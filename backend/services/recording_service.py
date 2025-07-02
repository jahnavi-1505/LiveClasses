import os
import aiohttp
import aiofiles
from fastapi import HTTPException
from sqlalchemy.orm import Session
from azure.storage.blob.aio import BlobServiceClient

from ..oauth_token import get_zoom_oauth_token
from ..models import ClassSession

def _ensure_session_exists(session_id: str, db: Session) -> ClassSession:
    sess = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

async def list_recordings(session_id: str, db: Session) -> list[dict]:
    sess = _ensure_session_exists(session_id, db)
    token = await get_zoom_oauth_token()
    headers = {"Authorization": f"Bearer {token}"}
    out = []
    async with aiohttp.ClientSession(headers=headers) as client:
        for meet in sess.meetings:
            url = f"https://api.zoom.us/v2/meetings/{meet.id}/recordings"
            async with client.get(url) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for f in data.get("recording_files", []):
                    download_url = f"{f['download_url']}?access_token={token}"
                    out.append({
                        "meeting_id": meet.id,
                        "id": f.get("id"),
                        "file_type": f.get("file_type"),
                        "download_url": download_url,
                        "recording_start": f.get("recording_start"),
                        "recording_end": f.get("recording_end"),
                    })
    return out

async def store_recordings_to_azure(session_id: str, db: Session) -> list[dict]:
    recs = await list_recordings(session_id, db)
    if not recs:
        raise HTTPException(status_code=404, detail="No recordings to upload")

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
    service = BlobServiceClient.from_connection_string(conn_str)
    container = service.get_container_client("recordings")

    stored = []
    token = await get_zoom_oauth_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession(headers=headers) as client:
        for rec in recs:
            url = rec["download_url"]
            content = None

            # Try bearer header
            async with client.get(url) as dl:
                if dl.status == 200:
                    content = await dl.read()

            # Try token param
            if content is None:
                async with client.get(f"{url}?download_access_token={token}") as dl2:
                    if dl2.status == 200:
                        content = await dl2.read()

            # Try no-auth
            if content is None:
                async with aiohttp.ClientSession() as no_auth:
                    async with no_auth.get(url) as dl3:
                        if dl3.status == 200:
                            content = await dl3.read()

            if not content:
                continue

            ext = rec["file_type"].lower()
            blob_name = f"{session_id}/{rec['meeting_id']}/{rec['id']}.{ext}"
            blob_client = container.get_blob_client(blob_name)
            await blob_client.upload_blob(content, overwrite=True)

            stored.append({
                "meeting_id": rec["meeting_id"],
                "file_id": rec["id"],
                "blob_path": blob_name,
                "file_size": len(content)
            })

    return stored

async def download_recordings_locally(session_id: str, db: Session) -> list[str]:
    recs = await list_recordings(session_id, db)
    if not recs:
        raise HTTPException(status_code=404, detail="No recordings to download")

    base_dir = os.path.join(os.getcwd(), "recordings", session_id)
    os.makedirs(base_dir, exist_ok=True)
    token = await get_zoom_oauth_token()
    saved = []

    async with aiohttp.ClientSession() as client:
        for rec in recs:
            url = rec["download_url"]
            data = None

            # 1) Bearer header
            async with client.get(url, headers={"Authorization": f"Bearer {token}"}, allow_redirects=True) as r1:
                if r1.status == 200:
                    data = await r1.read()

            # 2) token param
            if data is None:
                async with client.get(f"{url}?download_access_token={token}", allow_redirects=True) as r2:
                    if r2.status == 200:
                        data = await r2.read()

            # 3) no auth
            if data is None:
                async with aiohttp.ClientSession() as no_auth:
                    async with no_auth.get(url, allow_redirects=True) as r3:
                        if r3.status == 200:
                            data = await r3.read()

            if not data:
                continue

            meet_dir = os.path.join(base_dir, str(rec["meeting_id"]))
            os.makedirs(meet_dir, exist_ok=True)
            ext = rec["file_type"].lower()
            outpath = os.path.join(meet_dir, f"{rec['id']}.{ext}")
            async with aiofiles.open(outpath, "wb") as f:
                await f.write(data)
            saved.append(outpath)

    return saved
