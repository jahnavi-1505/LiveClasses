# backend/controllers/recordings.py

import os
import aiohttp
import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from azure.storage.blob.aio import BlobServiceClient

from ..database import get_db
from ..services.recording_service import list_recordings, store_recordings_to_azure, download_recordings_locally

router = APIRouter(prefix="/sessions/{session_id}", tags=["recordings"])

@router.get("/recordings")
async def get_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Return Zoom metadata and list of Azure-stored blob names.
    """
    # Fetch Zoom recording metadata
    zoom_list = await list_recordings(session_id, db)

    # List Azure blobs asynchronously
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
    service = BlobServiceClient.from_connection_string(conn_str)
    container = service.get_container_client("recordings")
    blobs = []
    async for blob in container.list_blobs(name_starts_with=f"{session_id}/"):
        blobs.append(blob.name)

    return {
      "recordings": zoom_list,     
      "azure_blobs": blobs         
    }

@router.post("/recordings/store")
async def store_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Download Zoom recordings and upload them to Azure Blob Storage.
    """
    stored = await store_recordings_to_azure(session_id, db)
    return {"stored": stored}

@router.post("/recordings/download")
async def download_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Download Zoom recordings to the local filesystem.
    """
    downloaded_files = await download_recordings_locally(session_id, db)
    return {"downloaded_files": downloaded_files}
