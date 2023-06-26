import logging
from datetime import datetime, time
import pytz

from ..auth import IBAuth
from ..rest import Accounts, MarketData, Portfolio, Trsrv
from ..session import IBSession
from ..storage import AbstractSessionStorage, FileStorage

log = logging.getLogger("ib.thin_client")


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

    def ibkr_long_break(self, dt=None):
        """
        Долгий перерыв с полной перезагрузкой.
        Ничего не работает. После перерыва требуется обновление сессии.

        Friday, 20:00 - 23:59 US/Pacific
        """
        dt = dt or datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = dt.astimezone(tz=pytz.timezone("US/Pacific"))

        return dt.isoweekday() == 5 and dt.time() >= time(20, 0)

    def ibkr_short_break(self, dt=None):
        """
        Короткий перерыв с легкой перезагрузкой.
        Сервисы по очереди отключаются на несколько минут.
        Сессия не сбрасывается.

        Sat - Thu, 20:45 - 21:45 US/Pacific
        Every day, 00:00 - 00:03 US/Pacific
        """
        dt = dt or datetime.utcnow().replace(tzinfo=pytz.utc)
        dt = dt.astimezone(tz=pytz.timezone("US/Pacific"))

        reboot = dt.isoweekday() != 5 and (time(20, 45) <= dt.time() <= time(21, 45))
        midnight = time(0, 0) <= dt.time() <= time(0, 3)

        return reboot or midnight
