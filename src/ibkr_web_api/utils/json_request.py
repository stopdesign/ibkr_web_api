import json
import logging
from dataclasses import dataclass
from typing import Any

import requests
from termcolor import colored, cprint

log = logging.getLogger("ib.request")


@dataclass
class JSONRequest:
    status_code: int = 0
    text: str = None
    json: Any = None
    error: str = None
    exception: Exception = None
    cookies = None

    debug = False

    def __init__(self, session, **params):

        try:
            resp = session.request(**params)

            self.status_code = resp.status_code or 0
            self.cookies = resp.cookies

            if self.debug:
                cprint(f"RESPONSE STATUS: {resp.status_code}", "cyan")

                # cprint("RESPONSE HEADERS:", "white", end=" ")
                # cprint(json.dumps(dict(resp.headers), indent=2), "white")

                cprint("RESPONSE COOKIES:", "magenta", end=" ")
                cprint(json.dumps(resp.cookies.get_dict(), indent=2), "magenta")

            if self.status_code and self.status_code != 200:
                self.text = str(resp.text)[:100]

            resp.raise_for_status()

            self.json = resp.json()

            if self.debug:
                cprint(f"RESPONSE: {resp.text}", "white")

        except requests.exceptions.HTTPError as e:
            self.error = "HTTPError"
            self.exception = e

        except requests.exceptions.ConnectionError as e:
            self.error = "ConnectionError"
            self.exception = e

        except requests.exceptions.Timeout as e:
            self.error = "Timeout"
            self.exception = e

        except json.decoder.JSONDecodeError as e:
            self.error = "JSONDecodeError"
            self.exception = e

        except requests.exceptions.RequestException as e:
            self.error = "RequestException"
            self.exception = e

        except Exception as e:
            log.exception(e)
            self.error = "Exception"
            self.exception = e

        if self.error:
            url = params.get("url")
            if self.status_code:
                txt = json.dumps(self.json) if self.json else self.text
                log.error(f"URL: {url}, status: {self.status_code}, response: {txt}")
            elif self.error != "Exception":
                log.error(f"{self.error}: {url}")
            else:
                log.error(f"{self.exception}", "magenta")
