import logging
from datetime import datetime
from time import sleep

from .auth import IBAuth
from .errors import IserverError, SSOError
from .rest import Accounts, Iserver, MarketData
from .session import IBSession
from .storage import AbstractSessionStorage, FileStorage, RedisStorage

log = logging.getLogger("ib_client")


class IBThinClient:
    """
    Базовый клиент. Использует готовую сессию из session_storage.
    """

    _auth: IBAuth
    _session: IBSession
    _storage: AbstractSessionStorage

    def __init__(self, session_id) -> None:

        # Перманентное хранилище сессии
        self._storage = FileStorage(session_id)

        # Делает запросы и хранит состояние сессии
        self._session = IBSession(self._storage)

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
    def iserver(self) -> Iserver:
        """
        Initializes the `Iserver` object.
        """

        return Iserver(session=self._session)

    def load_session(self):
        self._session.load()

    def check_session(self):
        res = self.iserver.auth_status()
        if res.json:
            a = res.json.get("authenticated")
            c = res.json.get("competing")
            sso = True
            log.info(f"Authenticated: {a}, Competing: {c}")
        else:
            sso = False
            a = False
            c = None
            log.error("Can't get iserver session status")
        return sso, a, c

    def keep_connected(self):
        raise NotImplementedError("IBThinClient can't maintain authentication")


class IBClient(IBThinClient):
    """
    Может получать и обновлять сессию.
    """

    def __init__(self, username, password, paper, reauth=False) -> None:
        super().__init__(session_id=username)
        self._auth = IBAuth(self._session, username, password, paper)
        self._reauth = reauth

    def start_session(self):
        log.info("Start a new session")

        self._auth.start_sso_session()
        sleep(2)
        self._auth.sso_validate()
        sleep(2)
        self.iserver.reinit_session()
        sleep(2)

    def kick_session(self):
        try:
            # Пнуть сервер
            self.iserver.kick()
        except SSOError:
            # Принять решение о запуске новой SSO сессии.
            # Следить за количеством неудачных попыток.
            if self._reauth:
                self.start_session()
        except IserverError:
            # Неустранимая ошибка iserver — подождать
            pass
        except Exception:
            # Какая-то еще ошибка
            pass

    def check_session(self, kick=True):
        sso, authenticated, competing = super().check_session()
        if kick and not (sso and authenticated and not competing):
            self.kick_session()
            sso, authenticated, competing = super().check_session()
        return sso, authenticated, competing

    def keep_connected(self):
        """
        Поддерживает и восстанавливает соединение.
        """

        while dt := datetime.utcnow():

            if dt.minute == getattr(self, "_minute", -1):
                sleep(0.5)
                continue

            self._minute = dt.minute

            # if not self. _calendar.working:
            # continue

            self.kick_session()
