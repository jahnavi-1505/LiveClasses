# oauth_token.py
import os
import aiohttp
import asyncio
from dotenv import load_dotenv


load_dotenv()
CID    = os.getenv("client_id_Zoom")
SEC    = os.getenv("secret_zoom")
ACCTID = os.getenv("ZOOM_ACCOUNT_ID")

async def get_zoom_oauth_token():
    url = "https://zoom.us/oauth/token"
    params = {
        "grant_type": "account_credentials",
        "account_id": ACCTID
    }
    auth = aiohttp.BasicAuth(login=CID, password=SEC)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, auth=auth) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"Zoom OAuth failed: {resp.status} {text}")
            return (await resp.json())["access_token"]

if __name__=="__main__":
    token = asyncio.run(get_zoom_oauth_token())
    print(token)
