# ibkr_web_api
IBKR web API client

It is a prototype client for IBKR web API.

The goal is to obtain session cookies and use it for direct requesting the web API.
I believe this is the minimum required list of cookies:

* USERID
* XYZAB_AM.LOGIN 
* XYZAB — the same as XYZAB_AM.LOGIN
* cp — iserver session

At the moment, it only supports accounts without 2FA enabled.
There is some code for requesting and processing the second factor,
but I didn't get it working yet.

Be aware that base_url = "https://ndcdyn.interactivebrokers.com" is hardcoded in IbApi.
If you want to use the code from outside the US, you may change the domain name.
