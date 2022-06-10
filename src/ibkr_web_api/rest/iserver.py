import logging
from secrets import token_hex
from time import sleep

from ibkr_web_api.errors import IserverError, SomeError, SSOError

log = logging.getLogger("ib_iserver")


class Iserver:

    timezone = "xxx (Etc/UTC)"

    def __init__(self, session) -> None:
        self._session = session
        self.machine_id = token_hex(4)

    def auth_status(self):
        return self._session.json_request("/iserver/auth/status", "GET")

    def _init_session(self):
        url = "/iserver/auth/ssodh/init"
        data = {
            "machineId": self.machine_id,
            "compete": True,
            "useSecurityContext": True,
            "locale": "en_US",
            "tz": self.timezone,
        }
        return self._session.json_request(url, "POST", data=data)

    def tickle(self):
        return self._session.json_request("/tickle", "POST")

    def init_portal_session(self):
        """
        Кажется, эта штука требуется для старта iserver_session.
        Если так не сделать, то при живой SSO сессии
        iserver_auth_status возвращает fail про пароль,
        а init_iserver_session отваливается по таймауту или в 503.
        Возможно, это только для 2FA или для live-аккаунта.
        """
        return self._session.json_request("/ssodh/init", "GET")

    def reinit_session(self, num=10, pause=5):
        """
        Захватить iserver-сессию
        """
        self.init_portal_session()
        self.auth_status()  # на всякий случай
        for i in range(num):
            if i:
                sleep(pause)
            log.warning("Init iserver session")
            res = self._init_session()
            if res.status_code < 210:
                break
            log.warning(f"Init iserver session: {res.json}")
        else:
            log.warning("Can't init iserver session")
            raise IserverError()
    
    def _log_tickle_ok(self):
        cookies = []
        for c in self._session._session.cookies:
            if c.name in ["XYZAB", "cp", "portal"] or "cp." in c.name:
                value = str(c.value or "")[:8]
                cookies.append(f"{c.name}: {value}")
        log.info(f"Tickle OK: {', '.join(sorted(cookies))}")

    def kick(self):

        res = self.tickle()

        # TODO: Проверить, что authenticated=False не попадает в эту опцию
        if res.error or not res.json:
            if res.status_code == 401:
                raise SSOError()
            else:
                raise SomeError()

        # Проверить статус SSO
        if not res.json.get("session"):
            raise SSOError()

        # Проверить статус iserver
        iserver = res.json.get("iserver", {}).get("authStatus", {})

        if msg := str(iserver.get("message", "")).replace("\n", " "):
            log.warning(f"Iserver message: {msg}")

        if msg := str(iserver.get("fail", "")).replace("\n", " "):
            log.warning(f"Iserver fail: {msg}")

        if msg := str(iserver.get("prompts", "")).replace("\n", " "):
            log.warning(f"Iserver prompts: {msg}")

        if not iserver.get("authenticated"):
            log.warning("Iserver: not authenticated")
            self.reinit_session()

        elif iserver.get("competing"):
            log.warning("Iserver: competing")
            self.reinit_session()

        else:
            self._log_tickle_ok()
