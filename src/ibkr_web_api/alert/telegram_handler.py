import logging
import re

import requests

from .base_handler import BaseAlertHandler

log = logging.getLogger("ib.telegram")


class TelegramAlertHandler(BaseAlertHandler):
    def __init__(self, token: str, channel_id: int) -> None:
        super().__init__()
        self.token = str(token)
        self.channel_id = int(channel_id)

    def send(self, text: str) -> None:
        """
        send("message text")
        """

        if not self.token:
            return

        ansi_esc = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {
            "text": ansi_esc.sub("", text).replace("-", "−"),
            "chat_id": self.channel_id,
            "parse_mode": "html",
        }

        try:
            requests.post(url, data=data, timeout=3)
        except Exception as e:
            log.error(f"ERROR send telegram: {e}")
