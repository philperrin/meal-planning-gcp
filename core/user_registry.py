"""
User Registry and New User Sign-in Tracker.
Stores registered users in a Google Cloud Storage JSON file (with local fallback)
and emits structured Cloud Logging events when a new user signs in for the first time.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from config import Config

logger = logging.getLogger(__name__)

_storage_client = None

def _get_storage_client():
    """Initializes Google Cloud Storage client using Application Default Credentials."""
    global _storage_client
    if not Config.USER_REGISTRY_BUCKET or Config.STORAGE_MODE == "local" or Config.FLASK_ENV == "testing":
        return None
    if _storage_client is not None:
        return _storage_client
    try:
        from google.cloud import storage
        _storage_client = storage.Client(project=Config.PROJECT_ID)
        return _storage_client
    except Exception as e:
        logger.debug(f"Cloud Storage client initialization skipped/failed: {e}")
        return None


def load_user_registry() -> Dict[str, Any]:
    """
    Loads the user registry JSON from Google Cloud Storage or local fallback.
    Returns a dict mapping normalized email addresses to user record metadata.
    """
    client = _get_storage_client()
    if client and Config.USER_REGISTRY_BUCKET:
        try:
            bucket = client.bucket(Config.USER_REGISTRY_BUCKET)
            blob = bucket.blob(Config.USER_REGISTRY_FILE)
            if blob.exists():
                content = blob.download_as_text(encoding="utf-8")
                return json.loads(content)
            else:
                logger.info(f"Registry blob {Config.USER_REGISTRY_FILE} does not exist yet. Initializing empty.")
                return {}
        except Exception as e:
            logger.warning(f"Failed to load user registry from GCS bucket {Config.USER_REGISTRY_BUCKET}: {e}")

    # Fallback to local file
    local_path = Path(Config.LOCAL_USER_REGISTRY_PATH)
    if local_path.exists():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read local user registry at {local_path}: {e}")

    return {}

def save_user_registry(registry: Dict[str, Any]) -> bool:
    """
    Persists the updated user registry JSON to Google Cloud Storage (and local fallback).
    """
    serialized = json.dumps(registry, indent=2, ensure_ascii=False)
    saved_gcs = False

    client = _get_storage_client()
    if client and Config.USER_REGISTRY_BUCKET:
        try:
            bucket = client.bucket(Config.USER_REGISTRY_BUCKET)
            blob = bucket.blob(Config.USER_REGISTRY_FILE)
            blob.upload_from_string(serialized, content_type="application/json")
            saved_gcs = True
            logger.debug(f"Successfully saved user registry to GCS gs://{Config.USER_REGISTRY_BUCKET}/{Config.USER_REGISTRY_FILE}")
        except Exception as e:
            logger.warning(f"Could not persist user registry to GCS: {e}")

    # Always write to local backup as well
    try:
        local_path = Path(Config.LOCAL_USER_REGISTRY_PATH)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(serialized)
    except Exception as e:
        logger.debug(f"Could not persist local user registry backup: {e}")

    return saved_gcs

def record_user_login(user_profile: Dict[str, Any]) -> bool:
    """
    Records a user login event.
    If the user has never logged in before:
      - Adds user to the Cloud Storage registry
      - Emits a structured 'NEW_USER_SIGNUP' log entry with [NEW_USER_ALERT] marker
        designed for Google Cloud Logging Alert Policies.
    Returns:
      True if this was a brand new user signup, False if returning user.
    """
    if not user_profile or not user_profile.get("email"):
        return False

    raw_email = user_profile.get("email", "").strip()
    user_email = raw_email.lower()
    user_name = user_profile.get("name", "Unknown User")
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        registry = load_user_registry()
        is_new_user = user_email not in registry

        if is_new_user:
            registry[user_email] = {
                "email": raw_email,
                "name": user_name,
                "first_login": now_iso,
                "last_login": now_iso,
                "login_count": 1,
            }
            save_user_registry(registry)

            # Emit structured log specifically tagged for GCP Cloud Logging alert filters
            log_payload = {
                "event": "NEW_USER_SIGNUP",
                "alert_tag": "[NEW_USER_ALERT]",
                "user_email": raw_email,
                "user_name": user_name,
                "timestamp": now_iso,
                "message": f"New user signup: {user_name} <{raw_email}>"
            }

            # Log formatted string and structured json
            logger.info(f"[NEW_USER_ALERT] NEW_USER_SIGNUP: {user_name} ({raw_email}) has signed in for the first time.", extra={"json_fields": log_payload})
            # Also write single-line JSON log for Cloud Run standard output parsing
            print(json.dumps({
                "severity": "NOTICE",
                "event": "NEW_USER_SIGNUP",
                "alert_tag": "[NEW_USER_ALERT]",
                "user_email": raw_email,
                "user_name": user_name,
                "timestamp": now_iso,
                "message": f"[NEW_USER_ALERT] New user signup: {user_name} <{raw_email}>"
            }), flush=True)

            return True
        else:
            # Existing user
            user_entry = registry[user_email]
            user_entry["last_login"] = now_iso
            user_entry["login_count"] = user_entry.get("login_count", 0) + 1
            if user_name and user_name != "Unknown User":
                user_entry["name"] = user_name
            save_user_registry(registry)

            logger.info(f"USER_LOGIN: Returning user {user_name} ({raw_email}) - Login #{user_entry['login_count']}")
            return False

    except Exception as e:
        logger.error(f"Error while updating user registry for {user_email}: {e}", exc_info=True)
        return False
