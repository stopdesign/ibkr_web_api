import json
import logging
from dataclasses import dataclass
from typing import Any

import requests
from termcolor import colored, cprint

log = logging.getLogger("ib_response")


@dataclass
class Response:
    status_code: int = None
    text: str = None
    json: Any = None
    error: str = None
    exception: Exception = None
    cookies = None

    debug = False

    @classmethod
    def from_requests(cls, resp):

        self = cls()

        self.status_code = resp.status_code
        self.cookies = resp.cookies

        try:
            if self.debug:
                cprint(f"RESPONSE STATUS: {resp.status_code}", "cyan")

                # cprint("RESPONSE HEADERS:", "white", end=" ")
                # cprint(json.dumps(dict(resp.headers), indent=2), "white")

                cprint("RESPONSE COOKIES:", "magenta", end=" ")
                cprint(json.dumps(resp.cookies.get_dict(), indent=2), "magenta")

            if resp.status_code != 200:
                self.text = str(resp.text)[:100]

            resp.raise_for_status()

            self.json = resp.json()

            if self.debug:
                txt = json.dumps(self.json, indent=2, default=str)
                cprint(f"RESPONSE: {txt}", "white")

        except requests.exceptions.HTTPError as e:
            self.error = "http"
            self.exception = e

        except requests.exceptions.Timeout as e:
            self.error = "timeout"
            self.exception = e

        except json.decoder.JSONDecodeError as e:
            self.error = "json"
            self.exception = e

        except Exception as e:
            log.exception(e)
            self.error = "exception"
            self.exception = e

        if self.error:
            txt = json.dumps(self.json, indent=2, default=str)
            log.error(colored(txt, "red"))

        return self

    @classmethod
    def from_exception(cls, e):
        # self.cookies = cookiejar_from_dict({})
        return cls(error="exception", exception=e)
