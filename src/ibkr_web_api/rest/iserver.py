import logging
# from secrets import token_hex
from time import sleep

from ibkr_web_api.errors import IserverError, SomeError, SSOError

log = logging.getLogger("ib.iserver")


class Iserver:

    timezone = "xxx (America/Los_Angeles)"

    def __init__(self, session) -> None:
        self._session = session
        # self.machine_id = token_hex(4).upper()

    def _init_session(self):
        url = "/iserver/auth/ssodh/init"
        data = {
            # "machineId": self.machine_id,
            "compete": True,
            "useSecurityContext": True,
            "locale": "en_US",
            "tz": self.timezone,
        }
        return self._session.json_request(url, "POST", data=data)

    def auth_status(self):
        """
        401, если нет SSO.

        При "authenticated: false" возвращает только MAC.
        Если "connected: true", то возвращает serverInfo.
        Если при этом "authenticated: false", то внутри serverInfo пусто.
        Если всё работает, то будет полноценный serverInfo:
        { 
            serverName: "JisfN5024", 
            serverVersion: "Build 10.15.0m, Jun 6, 2022 2:57:10 PM"
        }
        Это же касается tickle.
        """
        return self._session.json_request("/iserver/auth/status", "GET")

    def tickle(self):
        """
        См. auth_status
        """
        return self._session.json_request("/tickle", "POST")

    def init_portal_session(self):
        """
        Кажется, эта штука требуется для старта iserver_session.
        Если так не сделать, то при живой SSO сессии
        iserver_auth_status возвращает fail про пароль,
        а init_iserver_session отваливается в 503.
        Возможно, это только для 2FA или для live-аккаунта.
        """
        return self._session.json_request("/ssodh/init", "GET")

    # def portal_logout(self):
    #     return self._session.json_request("/logout", "POST")

    def reinit_session(self, num=5, pause=5):
        """
        Захватить iserver-сессию.
        """
        res = self.init_portal_session()
        log.info(f"Init portal session: {res}")

        # Без sleep _init_session иногда возвращает 503
        sleep(3)

        for i in range(1, num+1):
            if i > 1:
                log.info(f"Sleep {pause} sec...")
                sleep(pause)
            log.info(f"Init iserver session: attempt {i}/{num}")
            res = self._init_session()
            if 200 <= res.status_code < 210:
                log.info(f"Init iserver session: {res.json}")
                self._session.log_info()
                break
            else:
                log.warning(f"Init iserver session: {res}")

        else:
            log.warning("Can't init iserver session")
            raise IserverError()

    def kick(self):

        res = self.tickle()

        if res.error or not res.json:
            if res.status_code == 401:
                raise SSOError()
            else:
                raise SomeError(res.error)

        # Проверить статус SSO
        if not res.json.get("session"):
            raise SSOError()

        # Проверить статус iserver
        auth_status = res.json.get("iserver", {}).get("authStatus", {})

        # Вывести информацию про iserver, с которым работаем
        server_info = auth_status.get("serverInfo", {})
        name = server_info.get("serverName")
        version = server_info.get("serverVersion")
        log.info(f"MAC: {auth_status['MAC']}, name: {name}, version: {version}")

        if msg := str(auth_status.get("message", "")).replace("\n", " "):
            log.warning(f"Iserver message: {msg}")

        if msg := str(auth_status.get("fail", "")).replace("\n", " "):
            log.warning(f"Iserver fail: {msg}")

        if not auth_status.get("authenticated"):
            log.warning("Iserver: not authenticated")
            self.reinit_session()

        elif auth_status.get("competing"):
            log.warning("Iserver: competing")
            self.reinit_session()

        else:
            self._session.log_info()
