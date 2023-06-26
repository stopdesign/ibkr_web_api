import logging
from datetime import datetime, time
from time import sleep
import pytz

from ..alert import BaseAlertHandler
from ..auth import IBAuth
from ..errors import IserverError, SSOError
from ..rest import Accounts, Iserver, MarketData, Portfolio, Trsrv
from ..session import OAuthIBSession
from ..storage import AbstractSessionStorage, FileStorage

log = logging.getLogger("ib.oauth_client")


BASE_URLS = [
    "https://api.ibkr.com/v1/api",
]


class OAuthIBClient:
    """
    Базовый клиент. Может только читать сессию.
    """

    _auth: IBAuth
    _session: OAuthIBSession
    _storage: AbstractSessionStorage

    def __init__(self, consumer_key, oauth_access_token, live_session_token) -> None:

        self._ts = 0
        self._error_cnt = 0
        self._fatal_cnt = 0

        self._base_urls = BASE_URLS

        # Перманентное хранилище сессии
        # self._storage = storage or FileStorage(username)

        conf = {
            "consumer_key": consumer_key,
            "oauth_access_token": oauth_access_token,
            "live_session_token": live_session_token,
        }

        # Делает запросы и хранит состояние сессии
        self._session = OAuthIBSession(None, BASE_URLS[0], conf)

        # Расписание уборщицы IBKR
        # self._calendar = IBCalendar()

    @property
    def iserver(self) -> Iserver:
        """
        Initializes the `Iserver` object.
        Требуется клиент с правами на аутентификацию.
        """

        return Iserver(session=self._session)

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
        raise NotImplementedError()

    def start_session(self) -> None:
        raise NotImplementedError()

    def kick_session(self) -> None:
        raise NotImplementedError()

    def keep_connected(self) -> None:
        raise NotImplementedError()

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
