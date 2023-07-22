MQTT Chromium Control
=====================

Monitoring and control of a chromium browser via MQTT.
Connects to chrome using chrome debug protocol.

Intended for use with Home Assistant and a Chromium instance as kiosk.

Installation
------------

```
git clone https://github.com/functionpointer/mqtt-chromium-control.git
cd mqtt-chromium-control
python -m venv venv
pip install -r requirements.txt
```

Usage
-----

1. Launch your chrome with `--remote-debugging-port=9222 --remote-allow-origins=*`
More complete example:
```
/usr/bin/cage -- /usr/bin/chromium --enable-low-end-device-mode --renderer-process-limit=2 --disable-features=IsolateOrigins,site-per-process --disable-site-isolation-trials --noerrdialogs --disable-infobars --kiosk --remote-debugging-port=9222 --remote-allow-origins=* http://127.0.0.1:8123/dashboard-kiosk/0 &
```

2.

```
python -m mqtt_chromium_control
```

The program will connect to chrome and MQTT, and provide the following entities (with Home Assistant auto-discovery):
- Camera entity, showing a screenshot
- Sensor entity, containing size of the screenshot (useful for simple sanity check of displayed image)
- Button entity, causing chrome to load `about:blank` and then `http://127.0.0.1:8123` (configurable with `--tgt-url`)

For an overview of available options, run `python -m mqtt_chromium_control --help`


Systemd Service
---------------

There is an example `.service` file included.

It can be used like this:
```
ln -s $(pwd)/mqtt_chromium_control.service /etc/systemd/system/mqtt_chromium_control.service
systemctl daemon-reload
systemctl start mqtt_chromium_control
```
