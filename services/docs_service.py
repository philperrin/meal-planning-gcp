"""
Google Docs Service.
Creates on-demand formatted Google Docs for individual recipes,
saving them in the 'Meal Plan Recipes' folder in Google Drive.
Faithfully ported from Google Apps Script Code.gs (lines 1396-1465).
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from config import Config
from services.drive_service import get_or_create_folder
from core.exceptions import AppError

logger = logging.getLogger(__name__)

def create_recipe_doc(
    recipe_name: str,
    recipe: Dict[str, Any],
    diners_count: int,
    credentials: Credentials
) -> Dict[str, Any]:
    """
    Creates a standalone Google Doc on demand for a given recipe stored in db.recipeLibrary.
    Saves document in 'Meal Plan Recipes' folder in Drive and returns the docUrl and docId.
    """
    if not credentials:
        raise AppError("Google OAuth credentials are required to create Google Docs.")

    docs_service = build("docs", "v1", credentials=credentials, cache_discovery=False)
    drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    doc_id = recipe.get("docId")
    doc_url = recipe.get("docUrl")
    if doc_id and doc_url:
        try:
            f = drive_service.files().get(fileId=doc_id, fields="id, trashed").execute()
            if f and not f.get("trashed"):
                return {"success": True, "docUrl": doc_url, "docId": doc_id}
        except Exception:
            pass

    last_scheduled = recipe.get("lastScheduledDate", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    date_prefix = last_scheduled.replace("-", "") if last_scheduled else datetime.now(timezone.utc).strftime("%Y%m%d")
    doc_title = f"{date_prefix} - {recipe_name}"

    doc = docs_service.documents().create(body={"title": doc_title}).execute()
    new_doc_id = doc["documentId"]

    text_content = f"{recipe_name}\n"
    if recipe.get("description"):
        text_content += f"{recipe['description']}\n"
    text_content += f"Prep Time: {recipe.get('prepTime', '15m')} | Cook Time: {recipe.get('cookTime', '20m')}\n"
    text_content += f"Diners Scaled For: {recipe.get('originalDiners', diners_count)}\n\n"
    text_content += "Ingredients\n"
    for ing in recipe.get("ingredients", []):
        text_content += f"• {ing.get('amount', '')} {ing.get('unit', '')} {ing.get('name', '')}\n".replace("  ", " ")
    text_content += "\nInstructions\n"
    for idx, step in enumerate(recipe.get("instructions", [])):
        text_content += f"{idx + 1}. {step}\n"

    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": text_content
            }
        }
    ]

    docs_service.documents().batchUpdate(
        documentId=new_doc_id,
        body={"requests": requests}
    ).execute()

    parent_folder_id = get_or_create_folder(Config.PARENT_FOLDER_NAME, credentials)
    drive_service.files().update(
        fileId=new_doc_id,
        addParents=parent_folder_id,
        removeParents="root",
        fields="id, parents, webViewLink"
    ).execute()

    new_doc_url = f"https://docs.google.com/document/d/{new_doc_id}/edit"

    return {
        "success": True,
        "docUrl": new_doc_url,
        "docId": new_doc_id
    }
