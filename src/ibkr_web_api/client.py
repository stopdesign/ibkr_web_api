import logging
from datetime import datetime
from time import sleep

from .auth import IBAuth
from .errors import IserverError, SSOError
from .rest import Accounts, Iserver, MarketData, Portfolio
from .session import IBSession
from .storage import AbstractSessionStorage, FileStorage

log = logging.getLogger("ib.client")


BASE_URLS = [
    "https://gdcdyn.interactivebrokers.com",
    "https://cdcdyn.interactivebrokers.com",
    "https://ndcdyn.interactivebrokers.com",
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
        self._storage = storage if storage else FileStorage(username)

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

    def __init__(self, username, password, paper, storage=None) -> None:
        super().__init__(username=username, storage=storage)
        self._session.readonly = False
        self._auth = IBAuth(self._session, username, password, paper)

    @property
    def _iserver(self) -> Iserver:
        """
        Initializes the `Iserver` object.
        Требуется клиент с правами на аутентификацию.
        """

        return Iserver(session=self._session)

    def start_session(self) -> None:
        log.info("Starting a new session")

        self._auth.start_sso_session()
        sleep(2)

        self._auth.sso_validate()
        sleep(2)

        self._iserver.reinit_session()
        sleep(2)

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
        log.error(f"{reason} {self._fatal_cnt + 1}")

        print("\nALERT - ALERT - ALERT\n")

        if self._fatal_cnt:
            self.rotate_base_url()
        
        self._fatal_cnt += 1
        self._error_cnt = 0

        self.start_session()
        self._ts = 0

    def kick_session(self) -> None:
        """
        Дернуть соединение один раз.
        """
        try:
            self._iserver.kick()
            self._fatal_cnt = 0
            self._error_cnt = 0

        except SSOError:
            # Принять решение о запуске новой SSO сессии.
            self.fatal_error("SSO error")

        except IserverError:
            # Iserver никак не может соединиться.
            self.fatal_error("Fatal Iserver Error")

        except Exception as e:
            self._error_cnt += 1
            log.error(f"Iserver kick exception: {e}")

            if self._error_cnt > 10:
                self.fatal_error("Too Many Errors")

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

            # if not self. _calendar.working:
            # continue

            self.kick_session()
