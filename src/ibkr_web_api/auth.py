import json
import logging
import re
from datetime import datetime
from secrets import token_hex
from time import sleep
from urllib.parse import urlparse

from .session import IBSession
from .utils.ib_xyz import IBXyz

log = logging.getLogger("ib.auth")


def parse_xml_response(xml_string):
    """
    Парсит параметры из XML, игнорируя структуру.
    """
    return dict(re.findall(r"<(.+?)>(.*?)</", xml_string))


def default_2fa_handler(username, sf_challenge=None):
    if sf_challenge:
        print(f"Challenge for {username}:", sf_challenge.replace(" ", ""))
    response = input("2FA IBKey Response: ").strip()
    return response


class IBAuth:
    """ """

    _session: IBSession

    def __init__(self, session, username, password, paper=False):
        self._session = session

        self.username = username
        self.password = password
        self.login_type = 2 if paper else 1
        self.resp_two_fa = None

        self.ibkey_handler = default_2fa_handler
        self.sms_handler = default_2fa_handler

        if self._session.readonly:
            raise ValueError("IBAuth can't use readonly session")

    @property
    def xxx_password(self):
        return "x" * len(self.password)

    def start_sso_session(self):
        """
        Вся логика аутентификации до получения SSO-сессии.
        """
        self._xyz = IBXyz()
        self._session.reset_state()
        self._auth_prepare()
        self._auth_init()
        self._auth_completeauth()
        success = self._auth_dispatcher()
        if success:
            self._session.save()
        return success

    def sso_validate(self):
        return self._session.json_request("/sso/validate", "GET")

    def _auth_prepare(self):
        """
        Запрос страницы логина, получение JSESSIONID,
        инициализация SBID, обновление base_url и cookie_domain.
        """
        for i in range(10):
            r = self._session.auth_request("/sso/Login", "GET")

            if not (200 <= r.status_code < 400):
                raise Exception("Login page unavailable")

            # Здесь может быть серия редиректов с изменением домена
            if location := r.headers.get("Location"):
                loc = urlparse(location)
                self._session.base_url = f"{loc.scheme}://{loc.netloc}"
                continue

            self._session._session.cookies.set("SBID", None)
            self._session._session.cookies.set("SBID", token_hex(9))
            return

        raise Exception("Too many redirects on Login")

    def _auth_init(self):
        """
        Первый шаг аутентификации. Запрос криптографических параметров из IBKR.
        """
        data = {
            "ACTION": "INIT",
            "APP_NAME": "",
            "MODE": "NORMAL",
            "FORCE_LOGIN": "",
            "USER": self.username,
            "ACCT": "",
            "A": hex(self._xyz.big_a).lstrip("0x").rstrip("L"),
            "LOGIN_TYPE": self.login_type,
        }
        url = "/sso/Authenticator"

        r = self._session.auth_request(url, "POST", data=data, rand=True)
        crypto_params = parse_xml_response(r.text)

        log.debug(json.dumps(crypto_params, indent=2, default=str))

        # Обновить криптографические параметры по ответу от сервера
        self._xyz.update(crypto_params, self.username, self.password)

    def _auth_completeauth(self):
        """
        Второй шаг аутентификации.
        """
        data = {
            "ACTION": "COMPLETEAUTH",
            "APP_NAME": "",
            "USER": self.username,
            "ACCT": "",
            "M1": self._xyz.big_m1,
            "VERSION": "1",
            "LOGIN_TYPE": self.login_type,
            "EKX": self._xyz.ekx,
        }
        url = "/sso/Authenticator"
        r = self._session.auth_request(url, "POST", data=data, rand=True)
        params = parse_xml_response(r.text)

        log.debug(json.dumps(params, indent=2, default=str))

        # Удалить старые кукис и поставить новые
        self._session._session.cookies.set("XYZAB_AM.LOGIN", None)
        self._session._session.cookies.set("XYZAB_AM.LOGIN", self._xyz.sk)
        self._session._session.cookies.set("XYZAB", None)
        self._session._session.cookies.set("XYZAB", self._xyz.sk)

        # Сервер должен вернуть такой же M2
        assert params.get("M2") == self._xyz.big_m2, "Wrong password"

        # sftypes возвращает тип 2FA
        if sf_types := params.get("sftypes"):
            self._auth_second_factor(sf_types)
        else:
            log.info("No second factor")

    def _select_sf_type(self, sf_types):
        """
        Выбрать sf_type по приоритету.
        """
        sf_types = (sf_types or "").strip().split(",")
        for sf in ["5.2a", "5.2i", "4.2"]:
            if sf in sf_types:
                return sf
        return None

    def _auth_second_factor(self, sf_types):
        """
        Возможные типы:
        3 — SSC
        4 — ALPINE
        4.1 — DSC
        4.2 — SMS
        5 — PLAT_GOLD
        5.1 — DSC_PLUS
        5.2a — IBKEY_ANDROID
        5.2i — IBKEY_IOS
        5.3 — BANK_KEY
        6 — TSC
        """

        sf_type = self._select_sf_type(sf_types)

        if not sf_type:
            raise Exception(f"Unsupported 2FA types: {sf_types}")

        sf_challenge = self._auth_start_twofact(sf_type)

        log.info(f"2FA types: {sf_types}")
        log.info(f"2FA selected type: {sf_type}, challenge: {sf_challenge}")

        if sf_type == "5.2a":
            response = self.ibkey_handler(self.username, sf_challenge)
            self._auth_complete_twofact(sf_type, response)

        if sf_type == "4.2":
            response = self.sms_handler(self.username)
            self._auth_complete_twofact(sf_type, response)

        # Ждать нажатия кнопки в IBKey
        if sf_type == "5.2i":
            for i in range(100):
                sleep(6)
                if self._auth_complete_twofact_push(sf_type, i):
                    return
            raise Exception("2FA: no IBKey response")

    def _auth_start_twofact(self, sf_type):
        """
        Третий шаг — запрос кода 2FA.

        type:
            SWTK — SMS
            SWCR — приложение
        """
        data = {
            "ACTION": "COMPLETEAUTH_1",
            "APP_NAME": "",
            "USER": self.username,
            "ACCT": "",
            "M1": self._xyz.big_m1,
            "VERSION": "1",
            "SF": sf_type,
        }
        url = "/sso/Authenticator"
        r = self._session.auth_request(url, "POST", data=data, rand=True)
        params = parse_xml_response(r.text)

        if params.get("type") not in ["SWTK", "SWCR"]:
            raise Exception(f"Unknown 2FA type: {params}")

        return params.get("challenge")

    def _auth_complete_twofact(self, sf_type, response):
        """
        Проверка ответа 2FA
        """
        log.info(f"2FA response: {response}")

        data = {
            "ACTION": "COMPLETETWOFACT",
            "APP_NAME": "",
            "USER": self.username,
            "VERSION": "1",
            "SF": sf_type,
            "ACCT": "",
            "RESPONSE": response,
        }
        url = "/sso/Authenticator"
        r = self._session.auth_request(url, "POST", data=data, rand=True)
        params = parse_xml_response(r.text)

        if params.get("reached_max_login") == "true":
            raise Exception("2FA: failed login attempts limit reached")

        if params.get("auth_res") == "true":
            log.info("2FA DONE")
            self.resp_two_fa = response
            return True
        else:
            raise Exception(f"2FA: failed, {params}")

    def _auth_complete_twofact_push(self, sf_type, num):
        """
        Проверка ответа 2FA на Push в IBKey
        """
        data = {
            "ACTION": "COMPLETETWOFACT",
            "APP_NAME": "",
            "USER": self.username,
            "VERSION": "1",
            "SF": sf_type,
            "PUSH": "true",
            "counter": str(num + 1),
        }
        url = "/sso/Authenticator"
        r = self._session.auth_request(url, "POST", data=data, rand=True)
        params = parse_xml_response(r.text)

        if params.get("reached_max_login") == "true":
            raise Exception("2FA: failed login attempts limit reached")

        if params.get("auth_res") == "true":
            log.info("2FA DONE")
            self.resp_two_fa = ""
            return True
        else:
            log.info("Waiting for IBKey...")

        return False

    def _auth_dispatcher(self):
        """
        Финальная стадия аутентификации, должна выдать редирект на портал.
        """
        data = {
            "user_name": self.username,
            "password": self.xxx_password,
            "loginType": self.login_type,
            "M1": self._xyz.big_m1,
            "M2": self._xyz.big_m2,
        }
        url = "/sso/Dispatcher"

        if self.resp_two_fa is not None:
            data["chlginput"] = self.resp_two_fa

        r = self._session.auth_request(url, "POST", data=data)

        # Обработать цепочку редиректов
        while location := r.headers.get("Location"):
            log.info(f"Dispatcher redirect: {location}")
            try:
                r = self._session.auth_request(location, "GET")
            except Exception as e:
                log.error(f"Redirect error: {e}")
                break

        # Посмотреть, куда в итоге приехали.
        if r.status_code == 200 and "/portal/" in r.url:
            self.referer = r.url
            self._session.auth_time = datetime.utcnow().replace(microsecond=0)
            log.info(f"Dispatcher (SSO) DONE")
            return True
        else:
            log.error(f"Dispatcher (SSO) error: {r.status_code}, {r.url}")
            return False
