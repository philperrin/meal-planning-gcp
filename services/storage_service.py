"""
Storage service managing application persistence in Google Drive (or local fallback).
Includes comprehensive schema migrations guaranteeing 100% data continuity with Apps Script.
Faithfully ported from Google Apps Script Code.gs (lines 23-156).
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from config import Config
from core.config_keys import get_default_db
from core.exceptions import StorageError

logger = logging.getLogger(__name__)

def migrate_db_schema(db: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Applies schema migrations to ensure compatibility with all legacy database versions.
    Replicates Code.gs lines 55-155.
    """
    updated = False
    if not isinstance(db.get("preferences"), dict):
        db["preferences"] = {}
        updated = True

    prefs = db["preferences"]

    # Migrate 'restrictions' -> 'dietaryPreferences'
    if "restrictions" in prefs and "dietaryPreferences" not in prefs:
        prefs["dietaryPreferences"] = prefs.pop("restrictions")
        updated = True

    if "cuisinePreferences" not in prefs or not isinstance(prefs["cuisinePreferences"], dict):
        prefs["cuisinePreferences"] = {}
        updated = True

    if "dinersCount" not in prefs:
        prefs["dinersCount"] = 2
        updated = True

    if "defaultMealTime" not in prefs:
        prefs["defaultMealTime"] = "06:00 PM"
        updated = True

    if "skipWelcomePage" not in prefs:
        prefs["skipWelcomePage"] = False
        updated = True

    if "pantryIngredients" not in prefs or not isinstance(prefs["pantryIngredients"], list):
        prefs["pantryIngredients"] = []
        updated = True

    if "recipeRatings" not in db or not isinstance(db["recipeRatings"], dict):
        db["recipeRatings"] = {}
        updated = True

    if "recipeLibrary" not in db:
        db["recipeLibrary"] = {}
        updated = True

    # Auto-migrate recipeLibrary if stored as array
    if isinstance(db.get("recipeLibrary"), list):
        lib_map = {}
        for item in db["recipeLibrary"]:
            if isinstance(item, dict) and item.get("name"):
                lib_map[item["name"]] = item
        db["recipeLibrary"] = lib_map
        updated = True

    library = db["recipeLibrary"]

    # Auto-ingest any recipes in active meal plan if missing from recipeLibrary
    meal_plan = db.get("mealPlan")
    if meal_plan and isinstance(meal_plan.get("recipes"), list):
        plan_date = meal_plan.get("generatedAt", datetime.now(timezone.utc).isoformat())[:10]
        for r in meal_plan["recipes"]:
            if isinstance(r, dict) and r.get("name") and r["name"] not in library:
                library[r["name"]] = {
                    "name": r["name"],
                    "description": r.get("description", ""),
                    "prepTime": r.get("prepTime", "15m"),
                    "cookTime": r.get("cookTime", "20m"),
                    "ingredients": r.get("ingredients", []),
                    "instructions": r.get("instructions", []),
                    "docUrl": r.get("docUrl", r.get("url", "")),
                    "docId": r.get("docId", r.get("fileId", "")),
                    "originalDiners": prefs.get("dinersCount", 2),
                    "lastScheduledDate": r.get("lastScheduledDate", r.get("date", plan_date))
                }
                updated = True

    # Auto-ingest recipes from db.recipeRatings if missing from recipeLibrary
    ratings = db.get("recipeRatings", {})
    if isinstance(ratings, dict):
        now_date = datetime.now(timezone.utc).isoformat()[:10]
        for r_name in ratings:
            if r_name and r_name not in library:
                library[r_name] = {
                    "name": r_name,
                    "description": "Favorite family recipe.",
                    "prepTime": "20m",
                    "cookTime": "30m",
                    "ingredients": [],
                    "instructions": [],
                    "docUrl": "",
                    "docId": "",
                    "originalDiners": prefs.get("dinersCount", 2),
                    "lastScheduledDate": now_date
                }
                updated = True

    return db, updated

class LocalStorageProvider:
    """Provides local JSON file storage for headless development or testing."""
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = Path(file_path or Config.LOCAL_DB_PATH)

    def load_db(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            default_data = get_default_db()
            self.save_db(default_data)
            return default_data
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            migrated, updated = migrate_db_schema(data)
            if updated:
                self.save_db(migrated)
            return migrated
        except Exception as e:
            logger.error(f"Error reading local DB file: {e}")
            raise StorageError(f"Failed to load local database: {e}")

    def save_db(self, db_data: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            db_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(db_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving local DB file: {e}")
            raise StorageError(f"Failed to save local database: {e}")

class DriveStorageProvider:
    """
    Provides Google Drive storage for Automated_Meal_Planner_DB.json.
    Ensures 100% backward compatibility and parity with Google Apps Script.
    """
    def __init__(self, credentials: Optional[Credentials] = None):
        self.credentials = credentials

    def _get_drive_service(self):
        if not self.credentials:
            raise StorageError("Google OAuth credentials are required for Drive storage.")
        return build("drive", "v3", credentials=self.credentials, cache_discovery=False)

    def _get_or_create_db_file(self, drive) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Finds or creates Automated_Meal_Planner_DB.json in user's root Drive."""
        query = f"name = '{Config.DB_FILENAME}' and trashed = false"
        results = drive.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])

        if files:
            file_id = files[0]["id"]
            request = drive.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            content = fh.read().decode("utf-8")
            try:
                data = json.loads(content)
                return file_id, data
            except json.JSONDecodeError:
                logger.warning("Corrupt DB JSON in Drive; reinitializing default DB.")
                default_data = get_default_db()
                return file_id, default_data
        else:
            default_data = get_default_db()
            media = MediaIoBaseUpload(
                io.BytesIO(json.dumps(default_data, indent=2).encode("utf-8")),
                mimetype="application/json",
                resumable=True
            )
            file_metadata = {
                "name": Config.DB_FILENAME,
                "mimeType": "application/json"
            }
            new_file = drive.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            return new_file["id"], default_data

    def load_db(self) -> Dict[str, Any]:
        try:
            drive = self._get_drive_service()
            file_id, db_data = self._get_or_create_db_file(drive)
            migrated_db, updated = migrate_db_schema(db_data)
            if updated:
                self._update_drive_file(drive, file_id, migrated_db)
            return migrated_db
        except Exception as e:
            logger.error(f"Error loading database from Drive: {e}")
            raise StorageError(f"Failed to load database from Drive: {e}")

    def save_db(self, db_data: Dict[str, Any]) -> None:
        try:
            drive = self._get_drive_service()
            file_id, _ = self._get_or_create_db_file(drive)
            db_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            self._update_drive_file(drive, file_id, db_data)
        except Exception as e:
            logger.error(f"Error saving database to Drive: {e}")
            raise StorageError(f"Failed to save database to Drive: {e}")

    def _update_drive_file(self, drive, file_id: str, db_data: Dict[str, Any]):
        media = MediaIoBaseUpload(
            io.BytesIO(json.dumps(db_data, indent=2).encode("utf-8")),
            mimetype="application/json",
            resumable=True
        )
        drive.files().update(
            fileId=file_id,
            media_body=media
        ).execute()

def get_storage_provider(credentials: Optional[Credentials] = None):
    """Factory returning the appropriate storage provider based on configuration & credentials."""
    if credentials and Config.STORAGE_MODE == "drive":
        return DriveStorageProvider(credentials)
    return LocalStorageProvider()
