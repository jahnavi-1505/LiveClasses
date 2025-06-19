import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from fastapi import HTTPException

# Load environment variables
load_dotenv()

# Existing variable names retained
CID    = os.getenv("client_id_Zoom")
SEC    = os.getenv("secret_zoom")
ACCTID = os.getenv("ZOOM_ACCOUNT_ID")

# Sanity check for credentials
if not (CID and SEC and ACCTID):
    raise RuntimeError(
        "Missing Zoom credentials: make sure client_id_Zoom, secret_zoom, and ZOOM_ACCOUNT_ID are set in your .env"
    )

async def get_zoom_oauth_token():
    """
    Fetches an OAuth token using Zoom account-level credentials
    """
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
                # Raise HTTPException for FastAPI compatibility
                raise HTTPException(
                    status_code=500,
                    detail=f"Zoom OAuth failed: {resp.status} {text}"
                )
            data = await resp.json()
            return data.get("access_token")

if __name__ == "__main__":
    # Quick CLI test
    token = asyncio.run(get_zoom_oauth_token())
    print("Zoom OAuth token:", token)
