import logging
from datetime import datetime, time
from time import sleep
import pytz

from .alert import BaseAlertHandler
from .auth import IBAuth
from .errors import IserverError, SSOError
from .rest import Accounts, Iserver, MarketData, Portfolio, Trsrv
from .session import IBSession
from .storage import AbstractSessionStorage, FileStorage

log = logging.getLogger("ib.client")


BASE_URLS = [
    "https://ndcdyn.interactivebrokers.com",
    "https://cdcdyn.interactivebrokers.com",
]


class IBThinClient:
    """
    Базовый клиент. Может только читать сессию.
    """

    _auth: IBAuth
    _session: IBSession
    _storage: AbstractSessionStorage

    def __init__(self, username, storage=None) -> None:

        self._ts = 0
        self._error_cnt = 0
        self._fatal_cnt = 0

        self._base_urls = BASE_URLS

        # Перманентное хранилище сессии
        self._storage = storage or FileStorage(username)

        # Делает запросы и хранит состояние сессии
        self._session = IBSession(self._storage, BASE_URLS[0], username)

        # Расписание уборщицы IBKR
        # self._calendar = IBCalendar()

    @property
    def accounts(self) -> Accounts:
        """
        Initializes the `Accounts` object.
        """

        return Accounts(session=self._session)

    @property
    def market_data(self) -> MarketData:
        """
        Initializes the `MarketData` object.
        """

        return MarketData(session=self._session)

    @property
    def trsrv(self) -> Trsrv:
        """
        Initializes the `Trsrv` object.
        """

        return Trsrv(session=self._session)

    @property
    def portfolio(self) -> Portfolio:
        """
        Initializes the `Portfolio` object.
        """

        return Portfolio(session=self._session)

    def load_session(self):
        self._session.load()

    def start_session(self) -> None:
        raise NotImplementedError("Use IBClient for authentication")

    def kick_session(self) -> None:
        raise NotImplementedError("Use IBClient for authentication")

    def keep_connected(self) -> None:
        raise NotImplementedError("Use IBClient for authentication")


class IBClient(IBThinClient):
    """
    Может получать и обновлять сессию.
    """

    def __init__(self, username, password, paper, storage=None, alert=None) -> None:
        super().__init__(username=username, storage=storage)
        self._session.readonly = False
        self._auth = IBAuth(self._session, username, password, paper)
        self._alert = alert or BaseAlertHandler()

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

        self._alert.send(f"IB alert {self._auth.username}. {txt}")

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
                self._alert.send(f"IB alert {self._auth.username}. OK now.")

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

            if self._error_cnt > 10:
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

    def ibkr_long_break(self, dt=None):
        """
        Долгий перерыв с полной перезагрузкой.

        Friday, 20:00 - 23:59 US/Pacific
        """
        dt = dt or datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = dt.astimezone(tz=pytz.timezone("US/Pacific"))
        
        return dt.isoweekday() == 5 and dt.time >= time(20, 00)

    def ibkr_short_break(self, dt=None):
        """
        Короткий перерыв с легкой перезагрузкой.
        Сессия не сбрасывается.

        Saturday - Thursday, 20:45 - 21:45 US/Pacific
        """
        dt = dt or datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = dt.astimezone(tz=pytz.timezone("US/Pacific"))

        return dt.isoweekday() != 5 and (time(20, 45) <= dt.time() <= time(21, 45))

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
