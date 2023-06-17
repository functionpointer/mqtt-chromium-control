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
        self.logger = logging.getLogger("mqtt")
        if topic_prefix[-1] == "/":
            raise ValueError("topic_prefix can't have trailing slash")
        self.topic_prefix = topic_prefix
        self.name = name
        self.reload_cb = reload_cb

        self.url = yarl.URL(mqtt_url)
        self.client: aiomqtt.Client | None = None

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
            topic=f"homeassistant/camera/{self.name}/screenshot",
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
            topic=f"homeassistant/sensor/{self.name}/screenshot_size",
            payload=json.dumps(
                {
                    "name": self.name + " screenshot size",
                    "unique_id": self.name + "_screenshot_size",
                    "device_class": "data_size",
                    "state_class": "measurement",
                    "unit_of_measurement": "bytes",
                    "force_update": True,
                    "state_topic": self.size_topic,
                    "availability_topic": self.availability_topic,
                    "device": self.device_info,
                }
            ),
            retain=True,
        )
        await client.publish(
            topic=f"homeassistant/button/{self.name}/reload",
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

    async def run_mqtt_until_fail(self) -> None:
        async with aiomqtt.Client(
            hostname=self.url.host,
            port=self.url.port or 1883,
            will=aiomqtt.Will(topic=self.availability_topic, payload="offline"),
        ) as client:
            self.client = client
            # publish auto-discovery
            await self._publish_auto_discovery(client)
            self.logger.info("connected")
            async with client.messages() as messages:
                await client.subscribe(self.reload_topic)
                async for _ in messages:
                    self.logger.info("received reload command")
                    try:
                        await self.reload_cb()
                    except Exception:
                        self.logger.exception("reloading failed")

    async def run(self):
        while True:
            try:
                await self.run_mqtt_until_fail()
            except aiomqtt.MqttError as e:
                self.logger.error("mqtt error: %s, reconnecting in 15s")
                await asyncio.sleep(15)

    async def publish_image(self, img: io.BytesIO) -> None:
        async with asyncio.timeout(25):
            while self.client is None:
                await asyncio.sleep(0.5)
        assert self.client is not None

        imagebytes = img.read()
        async with asyncio.TaskGroup():
            self.client.publish(topic=self.camera_topic, payload=imagebytes)
            self.client.publish(topic=self.size_topic, payload=len(imagebytes))
        self.logger.debug("image published")
