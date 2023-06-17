#! /usr/bin/env python3

import base64
from pathlib import Path
import pychrome
import logging
import sys
import datetime
from PIL import Image
import io

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
img_folder = Path(
    sys.argv[1] if len(sys.argv) > 1 else "/usr/share/nginx/html/screenshots/"
)


logging.info(f"connecting to browser...")
browser = pychrome.Browser(url="http://127.0.0.1:9222")

tab = browser.list_tab()[0]
logging.info(f"starting tab...")
tab.start()
logging.info(f"taking screenshot...")
img = tab.call_method("Page.captureScreenshot", format="jpeg")
imgbytes = base64.b64decode(img["data"])
tab.stop()
logging.info(f"received {len(imgbytes)} bytes")

pngdata = io.BytesIO(imgbytes)
pil_img = Image.open(pngdata)
newsize = (400, 240)  # tuple(ti//2 for ti in pil_img.size)
logging.info(f"resizing from {pil_img.size} to {newsize}")
pil_img = pil_img.resize(newsize, resample=Image.Resampling.BICUBIC)


img_path = img_folder / datetime.datetime.now().strftime(
    "%Y-%m-%d_%Hh%Mm%Ss_chrome.jpg"
)
pil_img.save(img_path, format="jpeg", optimize=True, quality=65)
logging.info(f"saved to {img_path}")
