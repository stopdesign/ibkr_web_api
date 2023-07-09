import hashlib
import hmac
import json
import logging
import urllib.parse
from base64 import b64decode, b64encode
from datetime import datetime
from secrets import token_hex

import requests
from termcolor import cprint

from ..utils.json_request import JSONRequest

log = logging.getLogger("ib.session")


timezone = "xxx (America/Los_Angeles)"


def sign_hmac(msg, key):
    sig = hmac.new(b64decode(key), msg=msg.encode(), digestmod=hashlib.sha256)
    return urllib.parse.quote_plus(b64encode(sig.digest()).decode())


def combine_params(method: str, url: str, data: dict) -> str:
    auth_params_str = ""
    auth_url = urllib.parse.quote_plus(url)
    for k, v in data.items():
        auth_params_str += f"{k}={v}&"
    auth_params_str = urllib.parse.quote_plus(auth_params_str.strip("&"))
    return f"{method}&{auth_url}&{auth_params_str}"


def get_auth_header(method, url, consumer_key, oauth_token, token_secret):
    nonce = token_hex(10)
    now = datetime.now()
    ts = int(now.timestamp())

    data = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature": "",
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(ts),
        "oauth_token": oauth_token,
    }
    data_copy = dict(data)
    del data_copy["oauth_signature"]
    base_string = combine_params(method, url, data_copy)

    data["oauth_signature"] = sign_hmac(base_string, token_secret)

    auth_data = "OAuth"
    for k, v in data.items():
        auth_data += f' {k}="{v}",'
    auth_data = auth_data.strip(",")

    return auth_data


class OAuthIBSession:
    """
    Подписывает oauth-запросы с использованием live_session_token.
    """

    auth_request_delay = 0.5
    request_timeout = 12  # после 10 секунд наступает 503
    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:96.0) "
        "Gecko/20100101 Firefox/96.0"
    )

    debug = False

    _session: requests.Session

    def __init__(self, session_storage, base_url, conf) -> None:
        self.base_url = base_url
        self.username = ""
        self.readonly = False

        self._conf = conf

        self.consumer_key = conf["consumer_key"]
        self.oauth_access_token = conf["oauth_access_token"]
        self.live_session_token = conf["live_session_token"]

    def json_request(self, url, method, data=None):
        full_url = f"{self.base_url}{url}"

        if self.debug:
            cprint(f"\n{method} {full_url}", attrs=["bold"])

        if self.debug:
            cprint("REQUEST DATA:", "green", end=" ")
            cprint(json.dumps(data, indent=2), "green")

        h = get_auth_header(
            method,
            full_url,
            self.consumer_key,
            self.oauth_access_token,
            self.live_session_token,
        )

        headers = {
            "Authorization": h,
            "User-Agent": self.user_agent,
        }

        self._session = requests.Session()

        if self.debug:
            cprint("REQUEST HEADERS:", "green")
            cprint(json.dumps(self._session.headers, indent=2, default=str), "green")

        params = {
            "method": method,
            "url": full_url,
            "json": data,
            "timeout": self.request_timeout,
            "allow_redirects": False,
            "headers": headers,
        }

        return JSONRequest(self._session, **params)
