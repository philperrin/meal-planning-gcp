"""
Drive Service managing folder discovery and file hierarchy in Google Drive.
Faithfully ported from Google Apps Script Code.gs (lines 1204-1225).
"""

import logging
from typing import Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from core.exceptions import StorageError

logger = logging.getLogger(__name__)

def get_drive_service(credentials: Credentials):
    if not credentials:
        raise StorageError("Google OAuth credentials are required for Drive operations.")
    return build("drive", "v3", credentials=credentials, cache_discovery=False)

def get_or_create_folder(folder_name: str, credentials: Credentials) -> str:
    """
    Finds or creates a root-level folder in the user's Google Drive by name.
    Returns the folder ID.
    """
    drive = get_drive_service(credentials)
    query = (
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{folder_name}' and trashed = false"
    )
    results = drive.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    folder = drive.files().create(
        body=file_metadata,
        fields="id"
    ).execute()
    return folder["id"]

def get_or_create_subfolder(parent_folder_id: str, subfolder_name: str, credentials: Credentials) -> str:
    """
    Finds or creates a subfolder within a parent folder.
    Returns the subfolder ID.
    """
    drive = get_drive_service(credentials)
    query = (
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{subfolder_name}' and '{parent_folder_id}' in parents and trashed = false"
    )
    results = drive.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    file_metadata = {
        "name": subfolder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id]
    }
    folder = drive.files().create(
        body=file_metadata,
        fields="id"
    ).execute()
    return folder["id"]
