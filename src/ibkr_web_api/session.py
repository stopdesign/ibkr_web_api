import json
import logging
import random
from datetime import datetime
from time import sleep

import requests
from termcolor import cprint

from .utils.response import Response

log = logging.getLogger("ib_session")


class IBSession:
    auth_request_delay = 0.5
    request_timeout = 10
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:96.0) "
        "Gecko/20100101 Firefox/96.0"
    )
    base_url = "https://ndcdyn.interactivebrokers.com"

    debug = False

    _session: requests.Session

    def __init__(self, session_storage) -> None:
        self._session_storage = session_storage
        self.reset_state()

    @property
    def portal_proxy_url(self):
        return f"{self.base_url}/portal.proxy/v1/portal"

    def reset_state(self):
        """
        Обнуление всего.
        """
        log.debug("Reset state")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "User-Agent": self.user_agent,
            }
        )
        self.resp_two_fa = None
        self.referer = None
        self.auth_time = None

    def auth_request(self, url, method, data=None, rand=None):
        """
        Запрос для процесса аутентификации.
        """

        if url and url[0] == "/":
            url = self.base_url + url

        # Добавление jsessionid к URL при аутентификации
        jsessionid = self._session.cookies.get("jsessionid")
        if method == "POST" and jsessionid:
            url += f";jsessionid={jsessionid}"

        # Добавление рандомного параметра к URL при аутентификации
        if rand:
            url += f"?{random.randint(1000, 100000)}"

        if self.debug:
            cprint(f"\n{method} {url}", attrs=["bold"])

        if self.debug:
            cprint("REQUEST DATA:", "green", end=" ")
            cprint(json.dumps(data, indent=2), "green")

        headers = dict(self._session.headers)
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        # if self.debug:
        #     cprint("REQUEST HEADERS:", "white", end=" ")
        #     cprint(json.dumps(dict(headers), indent=2), "white")

        if self.debug:
            cprint("REQUEST COOKIES:", "yellow", end=" ")
            cprint(json.dumps(self._session.cookies.get_dict(), indent=2), "yellow")

        params = {
            "method": method,
            "url": url,
            "data": data,
            "headers": headers,
            "timeout": self.request_timeout,
            "allow_redirects": False,
        }

        try:
            resp = self._session.request(**params)

            # Переустанавливаю cookies, чтобы удалить привязку к домену
            for k, v in resp.cookies.get_dict().items():
                self._session.cookies.set(k, None)
                self._session.cookies.set(k, v)

        except Exception as e:
            log.error(f"Request error: {e}")
            resp = requests.Response()
            resp.status_code = 0

        if self.debug:
            cprint(f"Status: {resp.status_code}, length: {len(resp.text)}", "cyan")

            # cprint("RESPONSE HEADERS:", "white", end=" ")
            # cprint(json.dumps(dict(resp.headers), indent=2, default=str), "white")

            cprint("RESPONSE COOKIES:", "magenta", end=" ")
            cprint(json.dumps(resp.cookies.get_dict(), indent=2), "magenta")

        sleep(self.auth_request_delay)

        return resp

    def json_request(self, url, method, data=None):
        """
        Обычно это запрос для взаимодействия с REST API.
        """

        if url and url[0] == "/":
            url = self.portal_proxy_url + url

        if self.debug:
            cprint(f"\n{method} {url}", attrs=["bold"])

        if self.debug:
            cprint("REQUEST DATA:", "green", end=" ")
            cprint(json.dumps(data, indent=2), "green")

        headers = dict(self._session.headers)

        portal_page_url = "/portal/?loginType=2&action=ACCT_MGMT_MAIN&clt=0"
        headers["Referer"] = self.base_url + portal_page_url

        if self.debug:
            cprint("REQUEST HEADERS:", "white", end=" ")
            cprint(json.dumps(dict(headers), indent=2), "white")

        if self.debug:
            cprint("REQUEST COOKIES:", "yellow", end=" ")
            cprint(json.dumps(self._session.cookies.get_dict(), indent=2), "yellow")

        params = {
            "method": method,
            "url": url,
            "json": data,
            "timeout": self.request_timeout,
            "allow_redirects": False,
        }

        try:
            response = Response.from_requests(self._session.request(**params))
        except Exception as e:
            response = Response.from_exception(e)

        if response.error:
            log.error(f"request error: {response.error}")

        if response.exception:
            log.error(f"request exception: {response.exception}")

        # Переустанавливаю cookies, чтобы удалить привязку к домену
        if response.cookies:
            for cookie in response.cookies:
                self._session.cookies.set(cookie.name, None)
                self._session.cookies.set(cookie.name, cookie.value)
            log.info("New cookies detected")
            self.save()

        return response

    def load(self):
        data = self._session_storage.load()

        if not data:
            log.warning("No session data")
            return False

        self.reset_state()

        for key, value in data.get("cookies", {}).items():
            self._session.cookies.set(key, value)

        if auth_time := data.get("auth_time"):
            self.auth_time = datetime.fromisoformat(auth_time)

        self.base_url = data.get("base_url") or self.base_url

        if bool(data):
            log.info("Session loaded")

        return bool(data)

    def save(self):
        cookies = self._session.cookies.get_dict()
        cookies = {k: v for k, v in cookies.items() if v != '""'}
        cookies = {k: v for k, v in cookies.items() if "AWSALBAPP" not in k}
        data = {
            "auth_time": self.auth_time,
            "base_url": self.base_url,
            "cookies": cookies,
            # TODO: сохранить referer
        }
        try:
            self._session_storage.save(data)
            log.info("Session saved")
        except Exception:
            log.exception("Session storage error")
