import asyncio
import io
import logging

import asyncio_mqtt as aiomqtt
import yarl
import json
from typing import Callable, Awaitable


class CommMqtt:
    def __init__(
        self,
        mqtt_url: str,
        topic_prefix: str,
        name: str,
        reload_cb: Callable[[], Awaitable[None]],
    ):
        self.logger = logging.getLogger("comm_mqtt")
        if topic_prefix[-1] == "/":
            raise ValueError("topic_prefix can't have trailing slash")
        self.topic_prefix = topic_prefix
        self.name = name
        self.reload_cb = reload_cb

        self.url = yarl.URL(mqtt_url)
        if self.url.scheme != "mqtt":
            raise ValueError("mqtt url must start with mqtt://")
        self.client: aiomqtt.Client | None = None

        self.go_offline_task = None

    @property
    def availability_topic(self) -> str:
        return self.topic_prefix + "/status"

    @property
    def camera_topic(self) -> str:
        return self.topic_prefix + "/camera"

    @property
    def size_topic(self) -> str:
        return self.topic_prefix + "/camera_size"

    @property
    def reload_topic(self) -> str:
        return self.topic_prefix + "/reload"

    @property
    def device_info(self) -> dict:
        return {
            "name": self.name,
            "identifiers": self.name,
        }

    async def _publish_auto_discovery(self, client: aiomqtt.Client):
        await client.publish(
            topic=f"homeassistant/camera/{self.name}/screenshot/config",
            payload=json.dumps(
                {
                    "name": self.name + " screenshot",
                    "unique_id": self.name + "_screenshot",
                    "topic": self.camera_topic,
                    "availability_topic": self.availability_topic,
                    "device": self.device_info,
                }
            ),
            retain=True,
        )
        await client.publish(
            topic=f"homeassistant/sensor/{self.name}/screenshot_size/config",
            payload=json.dumps(
                {
                    "name": self.name + " screenshot size",
                    "unique_id": self.name + "_screenshot_size",
                    "device_class": "data_size",
                    "state_class": "measurement",
                    "unit_of_measurement": "B",
                    "force_update": True,
                    "state_topic": self.size_topic,
                    "availability_topic": self.availability_topic,
                    "device": self.device_info,
                }
            ),
            retain=True,
        )
        await client.publish(
            topic=f"homeassistant/button/{self.name}/reload/config",
            payload=json.dumps(
                {
                    "name": self.name + " reload",
                    "unique_id": self.name + "_reload",
                    "command_topic": self.reload_topic,
                    "availability_topic": self.availability_topic,
                    "device": self.device_info,
                }
            ),
            retain=True,
        )

    async def _go_offline(self, sleeptime=80) -> None:
        await asyncio.sleep(sleeptime)
        if self.client is not None:
            self.logger.warning("going offline")
            await self.client.publish(topic=self.availability_topic, payload="offline")

    async def _heartbeat(self) -> None:
        if self.go_offline_task:
            self.go_offline_task.cancel()
        self.go_offline_task = asyncio.create_task(self._go_offline())
        await self.client.publish(topic=self.availability_topic, payload="online")

    async def run_mqtt_until_fail(self) -> None:
        self.logger.debug(f"connecting to {self.url.host} port {self.url.port or 1883}")
        async with aiomqtt.Client(
            hostname=self.url.host,
            port=self.url.port or 1883,
            will=aiomqtt.Will(topic=self.availability_topic, payload="offline"),
        ) as client:
            self.client = client
            self.go_offline_task = asyncio.create_task(self._go_offline(5))
            # publish auto-discovery
            await self._publish_auto_discovery(client)
            self.logger.info("connected")
            try:
                async with client.messages() as messages:
                    await client.subscribe(self.reload_topic)
                    async for _ in messages:
                        self.logger.info("received reload command")
                        try:
                            await self.reload_cb()
                        except Exception:
                            self.logger.exception("reloading failed")
            except asyncio.CancelledError as e:
                self.logger.error("cancel received, sending offline")
                await self.client.publish(
                    topic=self.availability_topic, payload="offline"
                )
                self.logger.debug("offline sent")
                raise e

    async def run(self):
        while True:
            try:
                await self.run_mqtt_until_fail()
            except aiomqtt.MqttError as e:
                self.logger.error("mqtt error: %s, reconnecting in 15s", e)
                if self.go_offline_task:
                    self.go_offline_task.cancel()
                await asyncio.sleep(15)

    async def publish_image(self, img: io.BytesIO) -> None:
        async with asyncio.timeout(25):
            while self.client is None:
                self.logger.debug("publish_image: waiting for client")
                await asyncio.sleep(1)
        assert self.client is not None
        self.logger.debug("publish_image: starting to publish...")
        img.seek(0)
        imagebytes = img.read()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                self.client.publish(topic=self.camera_topic, payload=imagebytes)
            )
            tg.create_task(
                self.client.publish(topic=self.size_topic, payload=len(imagebytes))
            )
            tg.create_task(self._heartbeat())
        self.logger.info(f"image with {len(imagebytes)} bytes published")
