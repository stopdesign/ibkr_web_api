import hashlib
import hmac
import logging
from base64 import b64decode, b64encode
from datetime import datetime
from secrets import randbits, token_hex
from urllib.parse import quote_plus

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from cryptography.hazmat.primitives.serialization import load_pem_parameters

from ..utils.json_request import JSONRequest

log = logging.getLogger("ib.oauth")


class OAuth:
    """
    Класс, занимающийся получением OAuth live session token в IBKR.
    Реализована их версия протокола по описанию из документа:
    https://www.interactivebrokers.com/webtradingapi/oauth.pdf
    """

    endpoint = "/oauth/live_session_token"
    request_timeout = 5

    def __init__(self, session) -> None:
        self._session = session

        conf = self._session._conf

        self.consumer_key = conf["consumer_key"]
        self.oauth_token = conf["oauth_access_token"]
        self.signature_key = conf["signature_key"]
        self.encryption_key = conf["encryption_key"]
        self.token_secret = conf["token_secret"]

        dh_params = conf["dh_params"]

        dh = load_pem_parameters(dh_params.encode())
        self.dh_prime = dh.parameter_numbers().p
        self.dh_generator = dh.parameter_numbers().g

    @property
    def url(self):
        return f"{self._session.base_url}{self.endpoint}"

    def generate_secret_int(self):
        return randbits(200)

    def _rsa_decrypt(self, token_secret: str):
        key = PKCS1_v1_5.new(RSA.import_key(self.encryption_key))
        return key.decrypt(b64decode(token_secret), bytes(0))

    def _sign_oauth(self, auth_params: str):
        key = pkcs1_15.new(RSA.import_key(self.signature_key))
        digest = SHA256.new(auth_params.encode("utf-8"))
        signature = key.sign(digest)
        return b64encode(signature).decode("utf-8")

    def _combine_params(self, method: str, url: str, data: dict) -> str:
        auth_params_str = ""
        auth_url = quote_plus(url)
        for k, v in data.items():
            auth_params_str += f"{k}={v}&"
        auth_params_str = quote_plus(auth_params_str.strip("&"))
        return f"{method}&{auth_url}&{auth_params_str}"

    def live_session_token(self, secret_int) -> JSONRequest:
        """
        Запрос live_session_token.
        """

        nonce = token_hex(10)
        timestamp = str(int(datetime.now().timestamp()))

        dh_challenge = pow(self.dh_generator, secret_int, self.dh_prime)

        method = "POST"
        data = {
            "diffie_hellman_challenge": f"{dh_challenge:0x}",
            "oauth_consumer_key": self.consumer_key,
            "oauth_nonce": nonce,
            "oauth_signature": "",
            "oauth_signature_method": "RSA-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_token": self.oauth_token,
            "realm": "limited_poa",
        }

        auth_params = self._rsa_decrypt(self.token_secret).hex()

        data_copy = dict(data)
        del data_copy["realm"]
        del data_copy["oauth_signature"]

        auth_params += self._combine_params(method, self.url, data_copy)

        data["oauth_signature"] = quote_plus(self._sign_oauth(auth_params))

        auth_header = "OAuth"
        for k, v in data.items():
            auth_header += f' {k}="{v}",'
        auth_header = auth_header.strip(",")

        # log.info(f"Secret Integer: {secret_int}\n")
        # log.info(f"Authorization: {auth_header}\n")

        headers = {"Authorization": auth_header}

        params = {
            "method": method,
            "url": self.url,
            "json": None,
            "timeout": self.request_timeout,
            "allow_redirects": False,
            "headers": headers,
        }

        # Сессия полностью сбрасывается, чтобы заголовки были без лишнего
        self._session._session = requests.Session()
        self._session._session.headers.update(headers)

        return JSONRequest(self._session._session, **params)

    def decrypt_lst(self, response, secret_int):
        """
        Расшифровка live_session_token.
        """
        log.info(f"lst response: {response}")

        B = response["diffie_hellman_response"]
        signature = response["live_session_token_signature"]
        token_exp = response["live_session_token_expiration"]

        token_exp_dt = datetime.utcfromtimestamp(int(token_exp) // 1000)

        K = pow(int(B, 16), secret_int, self.dh_prime)
        K_len = (8 + (K + (K < 0)).bit_length()) // 8
        K_big = K.to_bytes(K_len, "big", signed=True)

        token_secret_bytes = self._rsa_decrypt(self.token_secret)
        sig = hmac.new(K_big, token_secret_bytes, hashlib.sha1)
        token = b64encode(sig.digest()).decode()

        return token, token_exp_dt, signature

    def validate_token(self, token, signature):
        """
        Проверка live_session_token по token_signature.
        """

        msg = self.consumer_key.encode()
        sig_bytes = b64decode(token.encode())

        control_sig = hmac.new(sig_bytes, msg, hashlib.sha1)
        control_str = control_sig.hexdigest()

        return control_str and control_str == signature
