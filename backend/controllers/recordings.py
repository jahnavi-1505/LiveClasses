import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

from ..database import get_db
from ..services.recording_service import list_recordings, store_recordings_to_azure, download_recordings_locally

# Try matching the pattern of your other routers
router = APIRouter(prefix="/sessions/{session_id}", tags=["recordings"])

@router.get("/test")
async def test_recordings_router(session_id: str):
    """Test endpoint to verify routing works"""
    return {"message": f"Recordings router working for session {session_id}"}

@router.get("/recordings")
async def get_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Return Zoom metadata only.
    """
    try:
        zoom_list = await list_recordings(session_id, db)
        return {"recordings": zoom_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recordings/stream_urls")
async def get_stream_urls(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate SAS URLs for Azure-stored recordings so clients can stream them.
    Returns URLs matched to recording metadata.
    """
    try:
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            raise HTTPException(status_code=500, detail="AZURE_STORAGE_CONNECTION_STRING not set")

        # Parse connection string for account and key
        parts = dict(pair.split("=", 1) for pair in conn_str.split(";") if pair)
        account_name = parts.get("AccountName")
        account_key = parts.get("AccountKey")
        if not account_name or not account_key:
            raise HTTPException(status_code=500, detail="Invalid Azure storage connection string")

        # Get recording metadata first
        recordings = await list_recordings(session_id, db)
        
        # If no recordings from Zoom, return empty
        if not recordings:
            return {"recordings_with_streams": []}
        
        # Async client for listing blobs
        async with BlobServiceClient.from_connection_string(conn_str) as service:
            container = service.get_container_client("recordings")
            base_url = f"https://{account_name}.blob.core.windows.net/recordings"
            
            # Create a mapping of recording IDs to stream URLs
            recording_streams = []
            
            for recording in recordings:
                # Look for matching blob
                blob_name = f"{session_id}/{recording['meeting_id']}/{recording['id']}.{recording['file_type'].lower()}"
                
                try:
                    # Check if blob exists
                    blob_client = container.get_blob_client(blob_name)
                    await blob_client.get_blob_properties()
                    
                    # Generate SAS token
                    sas = generate_blob_sas(
                        account_name=account_name,
                        container_name="recordings",
                        blob_name=blob_name,
                        account_key=account_key,
                        permission=BlobSasPermissions(read=True),
                        expiry=datetime.utcnow() + timedelta(hours=1)
                    )
                    
                    stream_url = f"{base_url}/{blob_name}?{sas}"
                    recording_streams.append({
                        "recording_id": recording["id"],
                        "meeting_id": recording["meeting_id"],
                        "file_type": recording["file_type"],
                        "stream_url": stream_url,
                        "recording_start": recording["recording_start"],
                        "recording_end": recording["recording_end"]
                    })
                except Exception:
                    # Blob doesn't exist, skip
                    continue

        return {"recordings_with_streams": recording_streams}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recordings/store")
async def store_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Download Zoom recordings and upload them to Azure Blob Storage.
    """
    try:
        stored = await store_recordings_to_azure(session_id, db)
        return {"stored": stored}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recordings/download")
async def download_recordings(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Download Zoom recordings to the local filesystem.
    """
    try:
        downloaded_files = await download_recordings_locally(session_id, db)
        return {"downloaded_files": downloaded_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))