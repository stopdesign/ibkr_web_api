import logging
from datetime import datetime, time

import pytz

from ..rest import Accounts, Iserver, MarketData, OAuth, Portfolio, Trsrv
from ..session import OAuthIBSession
from ..storage import AbstractSessionStorage

log = logging.getLogger("ib.oauth_client")


BASE_URLS = [
    "https://api.ibkr.com/v1/api",
]


class OAuthIBClient:
    """
    Клиент.
    """

    _session: OAuthIBSession
    _storage: AbstractSessionStorage

    def __init__(
        self,
        consumer_key,
        oauth_access_token,
        *,
        live_session_token=None,
        dh_params=None,
        signature_key=None,
        encryption_key=None,
        token_secret=None,
    ) -> None:
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
            "dh_params": dh_params,
            "signature_key": signature_key,
            "encryption_key": encryption_key,
            "token_secret": token_secret,
        }

        # Делает запросы и хранит состояние сессии
        self._session = OAuthIBSession(None, BASE_URLS[0], conf)

        # Расписание уборщицы IBKR
        # self._calendar = IBCalendar()

    @property
    def oauth(self) -> OAuth:
        """
        Initializes the `OAuth` object.
        Требуется клиент с приватными ключами.
        """

        return OAuth(session=self._session)

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

    def start_session(self) -> None:
        """
        Получение и проверка live session token
        """
        log.info("Starting a new oauth live session")

        oauth = self.oauth

        secret_int = oauth.generate_secret_int()
        resp = oauth.live_session_token(secret_int)

        try:
            token, token_exp, signature = oauth.decrypt_lst(resp.json, secret_int)
        except:
            raise ValueError

        log.info(f"Token: {token}, exp: {token_exp}")

        if not oauth.validate_token(token, signature):
            raise ValueError("Token is invalid")

        # Полученный токен передается в сессию
        self._session.live_session_token = token

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
