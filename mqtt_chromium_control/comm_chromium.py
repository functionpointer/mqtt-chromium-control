import base64
import pychrome
import logging
import sys
import datetime
from PIL import Image
import io
import yarl
from dataclasses import dataclass


@dataclass
class ChromiumState:
    """Represents the state of the chrome browser at one point in time"""

    dt: datetime.datetime
    screenshot: io.BytesIO


class CommChromium:
    def __init__(self, chromium_url: str):
        self.logger = logging.getLogger("chromium")

        self.url = yarl.URL(chromium_url)
        self.browser: pychrome.Browser | None = None
        self.tab: pychrome.Tab | None = None

    def connect(self):
        self.logger.debug(f"connecting...")
        self.browser = pychrome.Browser(url="http://127.0.0.1:9222")
        self.logger.debug("starting tab...")
        tabs = self.browser.list_tab()
        if len(tabs) < 1:
            raise ValueError("chrome: no open tabs!")
        self.tab = tabs[0]
        self.tab.start()
        self.logger.info("connection established")

    def take_picture(self, new_size: tuple[int, int] = (400, 240)) -> io.BytesIO:
        self.logger.debug("capturing screenshot...")
        img = self.tab.call_method("Page.captureScreenshot", format="jpeg", _timeout=20)
        img_bytes = base64.b64decode(img["data"])
        with io.BytesIO(img_bytes) as f:
            pil_img = Image.open(f)
            pil_img = pil_img.resize(new_size, resample=Image.Resampling.BICUBIC)
            ret = io.BytesIO()
            pil_img.save(ret, format="jpeg", optimize=True, quality=65)
            return ret

    def navigate(self, tgt_url: str, hard_reload: bool = True) -> None:
        if hard_reload:
            self.logger.info(f"navigate to empty page...")
            self.tab.call_method("Page.navigate", url="about:blank", _timeout=1)
            self.logger.info(f"delay...")
            self.tab.wait(3)
        self.logger.info(f"navigate to {tgt_url}")
        self.tab.call_method("Page.navigate", url=tgt_url, _timeout=10)
