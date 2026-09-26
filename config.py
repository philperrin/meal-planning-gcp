"""
Configuration settings for the Meal Planning Assistant.
Loads settings from environment variables and provides sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Allow OAuth2 to execute over HTTP during local testing and relax scope formatting
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

BASE_DIR = Path(__file__).resolve().parent

class Config:
    PROJECT_ID = os.getenv("PROJECT_ID", "meal-planning-app-507921")
    PORT = int(os.getenv("PORT", 8080))
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod-meal-planner")
    
    # Session Cookie Configuration for reliable OAuth redirects
    SESSION_COOKIE_NAME = "meal_planner_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Enabled dynamically in HTTPS / Cloud Run proxy
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.6-flash")
    GEMINI_FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-1.5-flash"]
    GEMINI_MAX_RETRIES = 3
    GEMINI_INITIAL_RETRY_DELAY = 1.5
    
    # Google OAuth 2.0 Web Client
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    
    # OAuth Scopes required for Calendar, Drive file access, Docs, and User Profile
    GOOGLE_OAUTH_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
    ]
    
    # Workspace & Database Configuration
    DB_FILENAME = "Automated_Meal_Planner_DB.json"
    PARENT_FOLDER_NAME = "Meal Plan Recipes"
    STORAGE_MODE = os.getenv("STORAGE_MODE", "drive")  # 'drive' or 'local'
    LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", str(BASE_DIR / "data" / "Automated_Meal_Planner_DB.json"))
