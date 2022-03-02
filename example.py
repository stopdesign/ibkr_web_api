from datetime import datetime
from termcolor import cprint
from ibkr_web_api import IbApi


def main():

    # No 2FA
    username = "***"
    password = "***"

    ib = IbApi(username, password, paper=True, debug=False)

    cprint("\n\nREQUEST_LOGIN\n", "red")
    ib.request_login()

    cprint("\n\nREQUEST_INIT\n", "red")
    ib.request_init()

    cprint("\n\nREQUEST_COMPLETEAUTH\n", "red")
    ib.request_completeauth()

    cprint("\n\nREQUEST_DISPATHER\n", "red")
    ib.request_dispatcher()

    cprint("\n\nVALIDATE SSO\n", "red")
    ib.sso_validate()

    cprint("\n\nINIT_PORTAL_SESSION\n", "red")
    ib.init_portal_session()

    cprint("\n\nINIT_ISERVER_SESSION\n", "red")
    ib.init_iserver_session()

    cprint("\n\nACCOUNTS\n", "red")
    ib.accounts()

    cprint("\n\nHISTORY\n", "red")
    ib.history()

    print()
    ib.print_cookies()

    # OUTPUT should be something like that:
    # COOKIES: {
    #     "AKA_A2": "A",
    #     "SBID": "*****",
    #     "REGION": "ndcdyn",
    #     "URL_PARAM": "\"\"",
    #     "USERID": "*****",
    #     "XYZAB": "*****",
    #     "XYZAB_AM.LOGIN": "*****",
    #     "web": "*****",
    #     "ADRUM_BT1": "*****",
    #     "ADRUM_BTa": "*****",
    #     "IB_LANG": "en",
    #     "IS_MASTER": "false",
    #     "cp": "*****",
    #     "pastandalone": "",
    #     "JSESSIONID": "*****"
    # }


if __name__ == "__main__":
    dt = datetime.now()
    main()
    print(f"Done in {str(datetime.now() - dt)[:-7]}")
