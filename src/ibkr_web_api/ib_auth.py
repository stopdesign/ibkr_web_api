import json
import re
import random
from urllib.parse import urlparse

import requests
import logging
from datetime import datetime
from secrets import token_hex
from time import sleep
from termcolor import cprint
from . import IbXyz


log = logging.getLogger("ib_auth")


def ts_to_dt_utc(ts):
    return datetime.utcfromtimestamp(ts // 1000)


class IbApi:
    session: requests.Session
    cd = ".interactivebrokers.com"
    request_timeout = 5
    request_delay = 0.2
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
    )
    timezone = "xxx (Etc/UTC)"

    base_hostname = None
    base_url = None

    def __init__(
        self,
        username,
        password,
        session_storage,
        paper=False,
        debug=False,
    ):
        self.debug = debug
        self.username = username
        self.password = password
        self.login_type = 2 if paper else 1
        self.machine_id = token_hex(4)
        self.second_factor_type = None
        self.resp_two_fa = None
        self.jsessionid = None
        self.session_storage = session_storage

        self._detect_base_url()

        self.portal_url = "%s/portal.proxy/v1/portal" % self.base_url

        self.reset_session()
        self.xyz = IbXyz()

    def _detect_base_url(self):
        """
        Определяем базовый url в зависимости от геолокации
        """
        r = requests.get(
            'https://ndcdyn.interactivebrokers.com/sso/Login?RL=1&locale=en_US',
            headers={"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.109 Safari/537.36"},
            allow_redirects=False
        )
        location = r.headers.get('Location')
        if not location:
            self.base_hostname = 'ndcdyn.interactivebrokers.com'
        else:
            parsed = urlparse(location)
            self.base_hostname = parsed.netloc

        self.base_url = 'https://%s' % self.base_hostname

    def get_portal_url(self):
        "https://%s/portal.proxy/v1/portal" % self.base_hostname

    def get_websocket_url(self):
        return "wss://%s/portal.proxy/v1/portal/ws" % self.base_hostname

    @property
    def xxx_password(self):
        return "x" * len(self.password)

    @staticmethod
    def parse_xml_response(xml_string):
        """
        Парсит параметры из XML, игнорируя структуру.
        """
        return dict(re.findall(r"<(.+?)>(.*?)</", xml_string))

    @staticmethod
    def to_hex(val):
        return hex(val).lstrip("0x").rstrip("L")

    def reset_session(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{self.base_url}/sso/Login",
                "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            }
        )
        self.session.cookies.set("AKA_A2", "A", domain=self.cd)
        self.session.keepalive = False

    def print_cookies(self):
        cookies = self.session.cookies.get_dict()
        cprint("COOKIES:", "yellow", end=" ")
        cprint(json.dumps(cookies, indent=2), "yellow")

    def request(self, url, method, data=None, jsid=None, rand=None, is_json=None):
        """
        Запрос в IBKR
        """
        if self.debug:
            cprint("REQUEST DATA:", "green", end=" ")
            cprint(json.dumps(data, indent=2), "green")

        cookies = self.session.cookies.get_dict()

        if self.debug:
            cprint("REQUEST COOKIES:", "yellow", end=" ")
            cprint(json.dumps(cookies, indent=2), "yellow")

        headers = self.session.headers

        json_data = None
        if is_json:
            json_data = data
            data = None
            headers = {
                "Content-Type": "application/json",
            }

        if url and url[0] == "/":
            url = self.base_url + url

        if jsid:
            url += f";jsessionid={self.jsessionid}"

        if rand:
            url += "?" + str(random.randint(1000, 100000))

        params = {
            "method": method,
            "url": url,
            "data": data,
            "json": json_data,
            "headers": headers,
            "cookies": cookies,
            "timeout": self.request_timeout,
            "allow_redirects": False,
        }

        try:
            resp = self.session.request(**params)
        except Exception as e:
            log.error(f"Request error: {e}")
            resp = requests.Response()
            resp.status_code = 0

        if self.debug:
            cprint(f"Status: {resp.status_code}, length: {len(resp.text)}", "cyan")

            cprint("RESPONSE HEADERS:", "white", end=" ")
            cprint(json.dumps(dict(resp.headers), indent=2, default=str), "white")

            cprint("RESPONSE COOKIES:", "yellow", end=" ")
            cprint(json.dumps(resp.cookies.get_dict(), indent=2), "yellow")

        sleep(self.request_delay)

        return resp

    def iserver_request(self, url, method, data=None):
        if url and url[0] == "/":
            url = self.portal_url + url

        res_json = {}
        try:
            resp = self.request(url, method, data, is_json=True)
            resp.raise_for_status()

            try:
                res_json = resp.json()
                res_json["_ERROR"] = False
            except ValueError:
                res_json["_ERROR"] = "json"
        except requests.exceptions.HTTPError as e:
            log.error(f"HTTP: {e}")
            # log.exception(e)
            res_json["_ERROR"] = "http"
        except requests.exceptions.Timeout:
            res_json["_ERROR"] = "timeout"
        except Exception as e:
            log.exception(e)
            res_json["_ERROR"] = "exception"

        return res_json

    def request_login(self):
        """
        Запрос страницы логина, инициализация переменных.
        """
        self.request("/sso/Login", "GET")
        self.session.cookies.set("SBID", token_hex(9))
        self.jsessionid = self.session.cookies.get_dict()["JSESSIONID"]

    def request_init(self):
        """
        Первый шаг аутентификации. Запрос криптографических параметров из IBKR.
        """
        big_a_hex = IbApi.to_hex(self.xyz.big_a)
        data = {
            "ACTION": "INIT",
            "APP_NAME": "",
            "MODE": "NORMAL",
            "FORCE_LOGIN": "",
            "USER": self.username,
            "ACCT": "",
            "A": big_a_hex,
            "LOGIN_TYPE": self.login_type,
        }
        url = "/sso/Authenticator"

        r = self.request(url, "POST", data=data, jsid=True, rand=True)
        crypto_params = IbApi.parse_xml_response(r.text)

        if self.debug:
            cprint(json.dumps(crypto_params, indent=2, default=str), "blue")

        # Обновить криптографические параметры по ответу от сервера
        self.xyz.update(crypto_params, self.username, self.password)

    def request_completeauth(self):
        """
        Второй шаг аутентификации.
        """
        data = {
            "ACTION": "COMPLETEAUTH",
            "APP_NAME": "",
            "USER": self.username,
            "ACCT": "",
            "M1": self.xyz.big_m1,
            "VERSION": "1",
            "LOGIN_TYPE": self.login_type,
            "EKX": self.xyz.ekx,
        }
        url = "/sso/Authenticator"
        r = self.request(url, "POST", data=data, jsid=True, rand=True)
        params = IbApi.parse_xml_response(r.text)

        if self.debug:
            cprint(json.dumps(params, indent=2, default=str), "blue")

        # sftypes возвращает тип 2FA, который дальше требуется
        self.second_factor_type = params.get("sftypes")

        server_m2 = params.get("M2")

        # Поставить кукис
        self.session.cookies.set("XYZAB_AM.LOGIN", self.xyz.sk, domain=self.cd)
        self.session.cookies.set("XYZAB", self.xyz.sk, domain=self.cd)

        assert server_m2 == self.xyz.big_m2, "Не совпадают M2"

    def request_dispatcher(self):
        """
        Финальная стадия аутентификации, должна выдать редирект на портал.
        """
        data = {
            "user_name": self.username,
            "password": self.xxx_password,
            "loginType": self.login_type,
            "M1": self.xyz.big_m1,
            "M2": self.xyz.big_m2,
        }
        if self.resp_two_fa is not None:
            data["chlginput"] = self.resp_two_fa

        r = self.request("/sso/Dispatcher", "POST", data=data, jsid=True)

        if self.debug:
            with open("dispatcher.html", "w") as f:
                f.write(r.text)

        # id="ERRORMSG" >failed</div>

        assert len(r.text) < 20000, "DISPATCHER ERROR"

        # Обработать цепочку редиректов
        # Не обязательно ходить по всем редиректам.
        while location := r.headers.get("Location"):
            if self.debug:
                cprint(f"REDIRECT {location}", "blue")
            try:
                r = self.request(location, "GET")
            except Exception as e:
                cprint(f"Redirect error: {e}", "red")
                break

    def sso_validate(self):
        res = self.iserver_request("/sso/validate", "GET")
        if res.get("USER_ID") and res.get("RESULT"):
            cprint(f"SSO OK", "green")
        else:
            cprint(f"SSO ERROR", "red")
        return res

    def iserver_auth_status(self):
        res = self.iserver_request("/iserver/auth/status", "GET")
        if res.get("authenticated") and res.get("connected"):
            cprint("ISERVER AUTH OK", "green")
        else:
            fail = res.get("fail")
            error = res.get("_ERROR")
            cprint(f"ISERVER AUTH ERROR: {error}, fail: {fail}", "red")
        return res

    def init_portal_session(self):
        res = self.iserver_request("/ssodh/init", "GET")
        return res

    def portal_logout(self):
        res = self.iserver_request("/logout", "POST")
        return res

    def sso_logout(self):
        """
        sso_logout
        """
        cprint("LOGOUT and reset session", "red")
        try:
            self.request("/sso/Logout", "GET")
        except Exception as e:
            log.exception(e)
        self.reset_session()

    def reauthenticate(self, retry=5):
        url = "/iserver/auth/ssodh/init"
        for n in range(retry):
            if n > 0:
                sleep(5)
                cprint("Wait 5 sec...", "yellow")
            data = {
                "machineId": self.machine_id,
                "compete": True,
                "useSecurityContext": True,
                "locale": "en_US",
                "tz": self.timezone,
            }
            res = self.iserver_request(url, "POST", data=data)
            if res.get("authenticated"):
                return res
        return {"authenticated": False}

    def init_iserver_session(self):
        iserver_status = self.iserver_auth_status()
        if iserver_status.get("authenticated"):
            return iserver_status
        return self.reauthenticate()

    def accounts(self):
        res = self.iserver_request("/iserver/accounts", "GET")
        if accounts := res.get("accounts"):
            cprint(accounts, "green")
        else:
            cprint(json.dumps(res, indent=2, default=str), "yellow")
        return res

    def history(self):
        url = f"{self.portal_url}/iserver/marketdata/history"
        url += "?conid=508109460&period=30min&bar=10min&outsideRth=true"
        res = self.iserver_request(url, "GET")
        if res.get("startTime") and res.get("data"):
            cprint(f"History OK", "green")
        else:
            cprint(f"History ERROR", "red")
        return res

    def orders_nice(self):
        data = {"filters": []}
        url = "/iserver/account/orders"
        res = self.iserver_request(url, "GET", data=data)
        if orders := res.get("orders"):
            for order in orders:
                txt = (
                    "{acct}  {orderId}  {order_ref}   "
                    "{ticker:<5}  {status:<15}  "
                    "{sizeAndFills:>5}    ".format(**order)
                )
                print(f"{txt:<50}" + "{orderDesc}".format(**order))
            # print(json.dumps(order, indent=2, default=str))
        else:
            cprint(f"Orders ERROR", "red")
        return res

    def snapshot_useless(self):
        url = "/portal.proxy/v1/portal/iserver/marketdata/snapshot?conids=265598,265599"
        res = self.request(url, "GET", None, is_json=True)
        print(json.dumps(res.json(), indent=2, default=str))
        return res

    def snapshot_md(self):
        url = "/portal.proxy/v1/portal/md/snapshot?conids=461318791,461318792,265598"
        res = self.request(url, "GET", None, is_json=True)
        print(json.dumps(res.json(), indent=2, default=str))
        return res

    def cancel_all_orders(self, account):
        data = {"filters": []}
        url = "/iserver/account/orders"
        res = self.iserver_request(url, "GET", data=data)
        if orders := res.get("orders"):
            for order in orders:
                order_id = order.get("orderId")
                status = order.get("status")
                if order_id and status not in ["Inactive", "Cancelled", "Filled"]:
                    del_url = f"/iserver/account/{account}/order/{order_id}"
                    res1 = self.iserver_request(del_url, "DELETE", data=None)
                    print(res1)

    def order_details(self, order_id):
        url = f"/iserver/account/order/status/{order_id}"
        res = self.iserver_request(url, "GET")
        if orders := res.get("order_id"):
            print(json.dumps(res, indent=2, default=str))
            for order in orders:
                txt = (
                    "{orderId}  {order_ref}   {ticker:<5}  {status:<10}  "
                    "{sizeAndFills}".format(**order)
                )
                print(f"{txt:<50}" + "{orderDesc}".format(**order))
        else:
            cprint(f"Orders ERROR", "red")
        return res

    def contract_details(self, symbol):
        url = f"/portal.proxy/v1/portal/trsrv/futures?symbols={symbol}"
        res = self.request(url, "GET", data={}, is_json=True)
        if res.status_code == 200:
            print(json.dumps(res.json(), indent=2, default=str))
        else:
            print("ERROR", symbol, res.status_code, res.text)

    def positions_nice(self, account):
        url = f"/portal.proxy/v1/portal/portfolio/{account}/positions"
        res = self.request(url, "GET", data={}, is_json=True)
        if res.status_code == 200:
            for position in res.json():
                print(
                    "{acctId}  "
                    "{contractDesc:<20} "
                    "{position:>8} "
                    "{mktPrice:>10.2f} "
                    "{unrealizedPnl:>8}".format(**position)
                )
            # print(json.dumps(position, indent=2, default=str))
        else:
            print(res.status_code)
            print(res.text)
            cprint(f"Positions ERROR", "red")
        return res

    def tickle(self):
        """
        The tickle endpoint pings the server to prevent the session from ending.
        """
        res = self.iserver_request("/tickle", "POST")
        print("TICKLE", json.dumps(res, indent=None, default=str))
        # естественным образом почему-то не ставится кукис cp
        self.session.cookies.set("cp", None)
        cp = res.get("session")
        if cp and len(cp) == 32:
            self.session.cookies.set("cp", cp)
            self.save_session()
        return res

    def save_session(self):
        cookies = self.session.cookies.get_dict()

        try:
            self.session_storage.save(cookies)
        except Exception:
            log.exception('session storage error')

    def load_session(self):
        cookies_dict = self.session_storage.load()
        for key, value in cookies_dict.items():
            if key[0] == "_":
                continue
            self.session.cookies.set(key, value, domain=self.cd)

    def obtain_session(self):
        """
        Аутентификация.
        """
        try:
            self.reset_session()
            self.request_login()
            self.request_init()
            self.request_completeauth()
            self.request_dispatcher()
            self.sso_validate()
            self.init_portal_session()
            if self.init_iserver_session():
                self.save_session()
                return True
            else:
                cprint("No valid session", "red")
                return False
        except Exception as e:
            log.error("Can't obtain session")
            # log.exception(e)
            return False

    def keep_session_alive(self):
        while True:
            tickle = self.tickle()
            if tickle.get("_ERROR") is not False:
                cprint(f"Bad tickle status", "red")
                sleep(3)
                break
            if not tickle.get("iserver", {}).get("authStatus", {}).get("authenticated"):
                cprint("sesstion is not authenticated")
                break
            sleep(30)
