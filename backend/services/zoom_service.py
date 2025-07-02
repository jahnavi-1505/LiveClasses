# backend/services/zoom_service.py

import os
import aiohttp
from datetime import datetime, timedelta

# ← fix: import from the parent package
from ..oauth_token import get_zoom_oauth_token  
from ..utils.ics_utils import build_meeting_ics

ZOOM_USER_ID = os.getenv("ZOOM_USER_ID")
if not ZOOM_USER_ID:
    raise RuntimeError("ZOOM_USER_ID not set in environment")

async def create_zoom_meeting(subject: str, start: datetime, end: datetime) -> dict:
    token = await get_zoom_oauth_token()
    url = f"https://api.zoom.us/v2/users/{ZOOM_USER_ID}/meetings"
    payload = {
        "topic": subject,
        "type": 2,
        "start_time": start.isoformat(),
        "duration": int((end - start).total_seconds() / 60),
        "timezone": "UTC",
        "settings": {"auto_recording": "cloud"}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
