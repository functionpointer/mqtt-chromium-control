#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import sys
from .comm_chromium import CommChromium
from .comm_mqtt import CommMqtt
import asyncio_mqtt as aiomqtt
import pychrome

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="mqtt-chromium-control",
        description="control a chromium via mqtt, using chrome debug protocol",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="set loglevel to DEBUG"
    )
    parser.add_argument(
        "-m",
        "--mqtt",
        dest="mqtt_url",
        default="mqtt://127.0.0.1:1883",
        help="URL of mqtt broker",
    )
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        default="chromium",
        help="name for homeassistant and prefix for all topics",
    )
    parser.add_argument(
        "-c",
        "--chromium",
        dest="chromium_url",
        default="http://127.0.0.1:9222",
        help="URL of chromium browser",
    )
    parser.add_argument(
        "--tgt-url",
        dest="tgt_url",
        default="http://[::1]:8123",
        help="target url the browser should have open",
    )
    args = parser.parse_args()

    logging.basicConfig(
        stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO
    )

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    chrome = CommChromium(chromium_url=args.chromium_url)

    async def on_reload():
        try:
            chrome.navigate(args.tgt_url)
        except pychrome.PyChromeException as e:
            logging.warning(f"failed to reload chrome: {e}")

    mqtt = CommMqtt(
        mqtt_url=args.mqtt_url,
        topic_prefix=args.name,
        name=args.name,
        reload_cb=on_reload,
    )

    async def chrometask():
        while True:
            try:
                chrome.connect()
                while True:
                    try:
                        img = chrome.take_picture()
                        await mqtt.publish_image(img)
                    except (
                        pychrome.CallMethodException,
                        pychrome.TimeoutException,
                    ) as e:
                        logging.warning(f"failed to get image: {e}")
                    except (asyncio.TimeoutError, aiomqtt.MqttError) as e:
                        logging.warning(f"failed to publish image: {e}")
                    await asyncio.sleep(30)
            except pychrome.PyChromeException:
                logging.exception(msg="pychrome error, reconnecting in 15s")
                await asyncio.sleep(15)

    async def run():
        mqtt_task = asyncio.create_task(mqtt.run())
        await asyncio.sleep(1)  # give mqtt time to connect
        tasks = [
            mqtt_task,
            asyncio.create_task(chrometask()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        logging.warning(f"tasks {done} have finished!")

    asyncio.run(run())
