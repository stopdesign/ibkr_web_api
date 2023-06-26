import logging
from datetime import datetime, time
from time import sleep
import pytz

from ..alert import BaseAlertHandler
from ..auth import IBAuth
from ..errors import IserverError, SSOError
from ..rest import Accounts, Iserver, MarketData, Portfolio, Trsrv
from ..session import IBSession
from ..storage import AbstractSessionStorage, FileStorage

from .ib_thin_client import IBThinClient

log = logging.getLogger("ib.client")


class IBClient(IBThinClient):
    """
    Может получать и обновлять сессию.
    """

    def __init__(
        self, username, password, paper, storage=None, alert_handler=None
    ) -> None:
        super().__init__(username=username, storage=storage)
        self._session.readonly = False
        self._auth = IBAuth(self._session, username, password, paper)
        self._alert_handler = alert_handler or BaseAlertHandler()

    @property
    def _iserver(self) -> Iserver:
        """
        Initializes the `Iserver` object.
        Требуется клиент с правами на аутентификацию.
        """

        return Iserver(session=self._session)

    def check_bulletins(self):
        res = self._session.bulletins()
        if res.json:
            for message in res.json:
                log.warning(message)
        else:
            log.info("No bulletins")

    def rotate_base_url(self) -> None:
        self._base_urls = self._base_urls[1:] + self._base_urls[:1]
        self._session.base_url = self._base_urls[0]
        log.warning(f"Set base URL: {self._session.base_url}")

    def fatal_error(self, reason):
        txt = f"{reason}, cnt: {self._fatal_cnt + 1}"

        log.error(txt)

        self._alert_handler.send(f"IB alert {self._auth.username}. {txt}")

        if self._fatal_cnt:
            self.rotate_base_url()

        self._fatal_cnt += 1
        self._error_cnt = 0

    def kick_session(self) -> None:
        """
        Дернуть соединение один раз.
        """
        try:
            self._iserver.kick()

            # Раньше были ошибки, но kick прошел удачно
            if self._fatal_cnt:
                msg = f"IB alert {self._auth.username}. OK now."
                self._alert_handler.send(msg)

            self._fatal_cnt = 0
            self._error_cnt = 0

            return True

        except SSOError:
            # Принять решение о запуске новой SSO сессии.
            self.fatal_error("SSO error")
            return False

        except IserverError:
            # Iserver никак не может соединиться.
            self.fatal_error("Fatal Iserver Error")
            return False

        except Exception as e:
            self._error_cnt += 1
            log.error(f"Iserver kick exception: {e}")

            if self._error_cnt > 5:
                self.fatal_error("Too Many Errors")
                return False

            return True

    def start_session(self) -> None:
        log.info("Starting a new session")

        try:
            self._auth.start_sso_session()
        except Exception as e:
            log.error(f"auth.start_sso_session exception: {e}")
            return

        sleep(2)

        try:
            self._auth.sso_validate()
        except Exception as e:
            log.error(f"auth.sso_validate exception: {e}")
            return

        sleep(2)

        try:
            self._iserver.reinit_session()
        except Exception as e:
            log.error(f"iserver.reinit_session exception: {e}")
            return

    def keep_connected(self) -> None:
        """
        Поддерживает и восстанавливает соединение.
        Запускает kick_session по определенным секундам
        каждой минуты и сразу после запуска.
        """

        while ts := datetime.now().timestamp():

            if (self._ts and int(ts % 30)) or (ts - self._ts < 10):
                sleep(0.5)
                continue

            self._ts = ts

            if self.ibkr_long_break():
                log.info("IBKR Scheduled Maintenance")
                continue

            if self._fatal_cnt >= 3:
                msg = "Too many Fatal Errors, wait 1 hour"
                log.error(msg)
                self._alert_handler.send(msg)
                sleep(3600)
                self._fatal_cnt = 0
                self._error_cnt = 0
                continue

            # Пнуть iserver
            sso_ok = self.kick_session()

            # Если
            if not sso_ok:
                if self.ibkr_short_break():
                    log.info("IBKR Short Break")
                    sleep(30)

                sleep(5)
                self.start_session()
                sleep(2)
                self._ts = 0
