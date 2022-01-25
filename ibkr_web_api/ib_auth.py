import json
import random
import re
import requests
from secrets import token_hex
from time import sleep
from termcolor import cprint
from . import IbXyz


class IbApi:
    session = None
    cd = ".interactivebrokers.com"
    base_url = "https://ndcdyn.interactivebrokers.com"
    portal_url = f"{base_url}/portal.proxy/v1/portal"
    request_timeout = 5
    request_delay = 0.2
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
    )
    timezone = "xxx (America/Los_Angeles)"

    def __init__(self, username, password, paper=False, debug=False):
        self.debug = debug
        self.username = username
        self.password = password
        self.login_type = 2 if paper else 1
        self.machine_id = token_hex(4)
        self.second_factor_type = None
        self.resp_two_fa = None
        self.jsessionid = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/sso/Login",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        })
        self.session.cookies.set("AKA_A2", "A")
        self.session.keepalive = False
        self.xyz = IbXyz()

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

    def print_cookies(self):
        cookies = self.session.cookies.get_dict()
        cprint("COOKIES:", "yellow", end=" ")
        cprint(json.dumps(cookies, indent=2))

    def request(self, url, method, data=None, jsid=None, rand=None):
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

        if method == "POST":
            headers = {
                "Accept": "*/*",
            }
        else:
            headers = {
                "Accept": "text/html,application/xhtml+xml,"
                          "application/xml;q=0.9,*/*;q=0.8",
            }

        if url and url[0] == "/":
            url = self.base_url + url

        if jsid:
            url += f";jsessionid={self.jsessionid}"

        if rand:
            url += "?" + str(random.randint(1000, 100000))

        resp = self.session.request(
            method=method,
            url=url,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=self.request_timeout,
            allow_redirects=False,
        )

        if self.debug:
            cprint(f"Status: {resp.status_code}, length: {len(resp.text)}", "cyan")

            cprint("RESPONSE HEADERS:", "white", end=" ")
            cprint(json.dumps(dict(resp.headers), indent=2, default=str), "white")

            cprint("RESPONSE COOKIES:", "yellow", end=" ")
            cprint(json.dumps(resp.cookies.get_dict(), indent=2), "yellow")

        sleep(self.request_delay)

        return resp

    def request_login(self):
        """
        Запрос страницы логина, инициализация переменных.
        """
        url = "/sso/Login"
        r = self.request(url, "GET")

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

        cprint(json.dumps(params, indent=2, default=str), "blue")

        # sftypes возвращает тип 2FA, который дальше требуется
        self.second_factor_type = params.get("sftypes")

        server_m2 = params.get("M2")

        # Поставить кукис
        self.session.cookies.set("XYZAB_AM.LOGIN", self.xyz.sk, domain=self.cd)
        self.session.cookies.set("XYZAB", self.xyz.sk, domain=self.cd)

        assert server_m2 == self.xyz.big_m2, "Не совпадают M2"

        if self.second_factor_type == "4.2":
            self.request_completeauth_1()
            self.resp_two_fa = input("2FA").strip()
            self.request_complete_twofact_sms(self.resp_two_fa)

        # Ждать результата 2FA
        if self.second_factor_type == "5.2a":
            self.request_completeauth_1()
            self.resp_two_fa = ""
            for i in range(10):
                sleep(5)
                print("==== request_complete_twofact ====")
                res = self.request_complete_twofact_push()
                if res.get("auth_res") == "true":
                    print("2fa DONE")
                    break

    def request_completeauth_1(self):
        """
        Третий шаг — запрос кода 2FA
        """
        print("M:", self.xyz.big_m1)
        data = {
            "ACTION": "COMPLETEAUTH_1",
            "APP_NAME": "",
            "USER": self.username,
            "ACCT": "",
            "M1": self.xyz.big_m1,
            "VERSION": "1",
            "SF": self.second_factor_type,
        }
        url = "/sso/Authenticator"
        r = self.request(url, "POST", data=data, jsid=True, rand=True)
        params = IbApi.parse_xml_response(r.text)

        cprint(json.dumps(params, indent=2, default=str), "blue")

    def request_complete_twofact_sms(self, two_fa):
        """
        Проверка ответа 2FA
        """
        data = {
            "ACTION": "COMPLETETWOFACT",
            "APP_NAME": "",
            "USER": self.username,
            "ACCT": "",
            "RESPONSE": two_fa,
            "VERSION": "1",
            "SF": self.second_factor_type,
        }
        url = "/sso/Authenticator"
        r = self.request(url, "POST", data=data, jsid=True, rand=True)
        params = IbApi.parse_xml_response(r.text)

        cprint(json.dumps(params, indent=2, default=str), "blue")

        return params

    def request_complete_twofact_push(self):
        """
        Проверка ответа 2FA
        """
        data = {
            "ACTION": "COMPLETETWOFACT",
            "APP_NAME": "",
            "USER": self.username,
            "VERSION": "1",
            "SF": self.second_factor_type,
            "PUSH": True,
        }
        url = "/sso/Authenticator"
        r = self.request(url, "POST", data=data, jsid=True, rand=True)
        params = IbApi.parse_xml_response(r.text)

        cprint(json.dumps(params, indent=2, default=str), "blue")

        return params

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

        with open("dispatcher.html", "w") as f:
            f.write(r.text)

        # id="ERRORMSG" >failed</div>

        assert len(r.text) < 20000, "DISPATCHER ERROR"

        # Обработать цепочку редиректов
        while location := r.headers.get("Location"):
            cprint(f"\n\nREDIRECT {location}", "red")
            r = self.request(location, "GET")

    def validate_sso(self):
        url = f"{self.portal_url}/sso/validate"
        r = self.request(url, "GET")
        try:
            res_json = r.json()
        except Exception:
            print(r.status_code, r.text)
            return
        print(json.dumps(res_json, indent=2, default=str))

    def init_portal_session(self):
        init_portal_url = f"{self.portal_url}/ssodh/init"
        r = self.request(init_portal_url, "GET")
        try:
            res_json = r.json()
        except Exception:
            print(r.status_code, r.text)
            return
        print(json.dumps(res_json, indent=2, default=str))

    def init_iserver_session(self):
        """
        reauthenticate
        """
        status_url = f"{self.portal_url}/iserver/auth/status"
        reauthenticate_url = f"{self.portal_url}/iserver/auth/ssodh/init"
        try:
            r = self.session.post(status_url, json={}, timeout=5)
            # r = self.request(status_url, "GET")
            print(r.status_code, json.dumps(r.json(), indent=2, default=str))

            for n in range(5):
                if r.json().get("authenticated"):
                    break
                else:
                    cprint("REAUTHENTICATE", "red")
                    payload = {
                        "username": self.username,
                        "machineId": self.machine_id,
                        "compete": True,
                        "useSecurityContext": True,
                        "locale": "en_US",
                        "tz": self.timezone,
                    }
                    self.session.headers.update({
                        'Content-Type': "application/json; charset=utf-8",
                        'Referer': "https://ndcdyn.interactivebrokers.com/portal/",
                    })
                    r = self.session.post(reauthenticate_url, json=payload, timeout=5)
                    print(r.status_code, r.text)
                    sleep(1)
                    r = self.session.post(status_url, json={}, timeout=5)
                    print(r.status_code, json.dumps(r.json(), indent=2, default=str))
                sleep(3)
                print("-----------")

        except Exception as e:
            cprint(e, "red")

    def accounts(self):
        url = f"{self.portal_url}/iserver/accounts"
        r = self.request(url, "GET")
        try:
            res_json = r.json()
        except Exception:
            print(r.status_code, r.text)
            return
        print(json.dumps(res_json, indent=2, default=str))

    def history(self):
        url = f"{self.portal_url}/iserver/marketdata/history"
        url += "?conid=416904&period=30min&bar=10min&outsideRth=true"
        r = self.request(url, "GET")
        try:
            res_json = r.json()
        except Exception:
            print(r.status_code, r.text)
            return
        print(json.dumps(res_json, indent=2, default=str))

