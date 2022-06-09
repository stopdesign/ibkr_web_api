import codecs
import hashlib
from secrets import token_hex

# TODO: move to cryptography
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


class IBXyz:
    """
    IBKR cryptography
    """

    a = 0
    big_n = int(
        "d4c7f8a2b32c11b8fba9581ec4ba4f1b04215642ef7355e37c0fc0443ef756ea"
        "2c6b8eeb755a1c723027663caa265ef785b8ff6a9b35227a52d86633dbdfca43",
        16,
    )
    g = 2
    big_a = 0
    big_b = None
    rsapub = None
    salt = None
    hash = "SHA-1"
    proto = "6"

    def __init__(self):
        # set_random_a
        self.a = int(token_hex(32), 16)

        # recalc_big_a
        self.big_a = modular_pow(self.g, self.a, self.big_n)

        self.big_m1 = None
        self.big_m2 = None
        self.ekx = None
        self.sk = None

    @property
    def k(self) -> int:
        if self.proto == "3":
            return 1
        elif self.proto == "6":
            return 3
        raise NotImplemented

    @property
    def u(self) -> int:
        """
        proto: 3, 6, 6a
        """
        hashin = ""
        ahex = bigInt2radix(self.big_a)
        bhex = bigInt2radix(self.big_b)
        proto = self.proto
        if proto != "3":
            if proto == "6":
                if len(ahex) & 1 == 0:
                    hashin += ahex
                else:
                    hashin += "0" + ahex
        # else:  # 6a requires left-padding
        #     nlen = 2 * ((Nv.bitLength() + 7) >> 3)
        #     hashin += nzero(nlen - ahex.length) + ahex
        if proto == "3" or proto == "6":
            if len(bhex) & 1 == 0:
                hashin += bhex
            else:
                hashin += "0" + bhex
        # else { /* 6a requires left-padding; nlen already set above */
        #  hashin += nzero(nlen - bhex.length) + bhex;
        if proto == "3":
            utmp = calcSHA1Hex(hashin)[0:8]
        else:
            utmp = calcSHA1Hex(hashin)

        return int(utmp, 16)

    def xyz_compute_x(self, username: str, password: str) -> int:
        ih = calcSHA1(username + ":" + password)
        oh = calcSHA1Hex(verifyHexVal(self.salt) + ih)
        return int(oh, 16)

    def xyz_compute_m1(self, username, big_k):
        h_n = calcSHA1Hex(bigInt2radix(self.big_n))
        h_g = calcSHA1Hex(verifyHexVal(self.g))
        xor = int(h_n, 16) ^ int(h_g, 16)
        hashin = ""
        hashin += bigInt2radix(xor)
        hashin += calcSHA1(username)
        hashin += verifyHexVal(self.salt)
        hashin += verifyHexVal(self.big_a)
        hashin += verifyHexVal(self.big_b)
        hashin += verifyHexVal(big_k)
        return calcSHA1Hex(hashin)

    def xyz_compute_m2(self, big_m1, big_k):
        hashin = ""
        hashin += verifyHexVal(self.big_a)
        hashin += verifyHexVal(int(big_m1, 16))
        hashin += verifyHexVal(big_k)
        return calcSHA1Hex(hashin)

    def compute_sk(self, verifier):
        seed = self.big_b
        hashin = ""
        hashin += verifyHexVal(seed)
        hashin += verifyHexVal(verifier)
        return calcSHA1Hex(hashin)

    def update(self, params, username, password):
        self.proto = params["proto"]
        self.hash = params["hash"]
        self.salt = int(params["s"], 16)
        self.big_b = int(params["B"], 16)
        self.rsapub = int(params["rsapub"], 16)

        x = self.xyz_compute_x(username, password)
        sc = self.recalc_sc(x)
        big_k = int(calcSHA1Hex(bigInt2radix(sc)), 16)
        big_m1 = self.xyz_compute_m1(username, big_k)
        big_m2 = self.xyz_compute_m2(big_m1, big_k)
        ekx = self.do_encrypt(bigInt2radix(big_k))
        sk = self.compute_sk(big_k)

        self.big_m1 = big_m1
        self.big_m2 = big_m2
        self.ekx = ekx
        self.sk = sk

    def recalc_sc(self, x):
        bx = modular_pow(self.g, x, self.big_n)
        btmp = (self.big_b + self.big_n * self.k - bx * self.k) % self.big_n
        _exp = x * self.u + self.a
        sc = modular_pow(btmp, _exp, self.big_n)
        return sc

    def do_encrypt(self, value):
        key = RSA.construct((self.rsapub, 3))
        cipher = PKCS1_v1_5.new(key)
        res = cipher.encrypt(value.encode())
        return codecs.encode(res, "hex").decode()


def modular_pow(base, exponent, modulus):
    if modulus == 1:
        return 0
    else:
        result = 1
        base = base % modulus
        while exponent > 0:
            if exponent % 2 == 1:
                result = (result * base) % modulus
            exponent = exponent >> 1
            base = (base * base) % modulus
        return result


def bigInt2radix(val: int) -> str:
    return hex(val).lstrip("0x").rstrip("L")


def verifyHexVal(val):
    hashin = ""
    bhex = bigInt2radix(val)
    if len(bhex) & 1 == 0:
        hashin += bhex
    else:
        hashin += "0" + bhex
    # 20061106
    if hashin[0] == "0" and hashin[1] == "0":
        hashin = hashin[2:]
    return hashin


def calcSHA1Hex(val):
    val = bytes.fromhex(verifyHexVal(int(val, 16)))
    return hashlib.sha1(val).hexdigest()


def calcSHA1(val):
    return hashlib.sha1(val.encode()).hexdigest()


def logical_xor(str1, str2):
    return bool(str1) ^ bool(str2)
