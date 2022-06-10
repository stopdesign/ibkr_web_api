import json
from oath import OCRAChallengeResponseClient

# TODO: сделать класс, который сможет хранить настройки (путь)
# TODO: и методы загрузки-выгрузки конфига.

def ocra_handler(username, challenge):
    f_name = f"ocra_{username}.json"
    data = json.load(open(f_name))
    data["counter"] += 1
    ocra_key = bytes.fromhex(data["ocra_key"])
    challenge = str(challenge).replace(" ", "").strip()
    x = OCRAChallengeResponseClient(ocra_key, "OCRA-1:HOTP-SHA1-8:C-QN06-PSHA1")
    res = x.compute_response(challenge, C=data["counter"], P=data["pin"])
    json.dump(data, open(f_name, "w"), indent=2)
    return res
