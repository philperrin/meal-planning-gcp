"""
Google OAuth 2.0 Authentication & Token Lifecycle Manager.
Provides authorization URL generation, code-for-token exchange,
session token storage, and automatic token refresh.
"""

import os
import logging
from typing import Optional, Dict, Any
from flask import session, url_for, request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import googleapiclient.discovery

from config import Config
from core.exceptions import AuthRequiredError

# Allow OAuth2 to execute over HTTP during local testing and relax scope formatting
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

logger = logging.getLogger(__name__)

SESSION_TOKEN_KEY = "google_oauth_token"
SESSION_USER_KEY = "google_user_profile"

def create_oauth_flow(redirect_uri: Optional[str] = None, state: Optional[str] = None) -> Flow:
    """Creates a Google OAuth Flow instance configured with app credentials and scopes."""
    client_config = {
        "web": {
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    
    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=Config.GOOGLE_OAUTH_SCOPES,
        state=state
    )
    
    # Resolve redirect URI
    if not redirect_uri:
        if Config.GOOGLE_REDIRECT_URI:
            redirect_uri = Config.GOOGLE_REDIRECT_URI
        else:
            redirect_uri = url_for("views.auth_callback", _external=True)
            
    flow.redirect_uri = redirect_uri
    return flow

def get_authorization_url(redirect_uri: Optional[str] = None) -> tuple[str, str, Optional[str]]:
    """Generates the authorization URL, state token, and PKCE code_verifier for initiating Google Sign-In."""
    flow = create_oauth_flow(redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    code_verifier = getattr(flow, "code_verifier", None)
    return auth_url, state, code_verifier

def exchange_code_for_tokens(
    code: str,
    state: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    code_verifier: Optional[str] = None
) -> Dict[str, Any]:
    """Exchanges an authorization code for access and refresh tokens, saving to session."""
    flow = create_oauth_flow(redirect_uri, state=state)
    
    # Restore PKCE code verifier required by Google OAuth 2.0
    if not code_verifier:
        code_verifier = session.get("code_verifier")
    if code_verifier:
        flow.code_verifier = code_verifier
        
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    
    session[SESSION_TOKEN_KEY] = token_data
    
    # Fetch and cache basic user profile
    try:
        user_info_service = googleapiclient.discovery.build(
            "oauth2", "v2", credentials=creds, cache_discovery=False
        )
        user_info = user_info_service.userinfo().get().execute()
        session[SESSION_USER_KEY] = {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
        }
    except Exception as e:
        logger.warning(f"Could not retrieve user info after token exchange: {e}")
        session[SESSION_USER_KEY] = {"email": "user@google.com", "name": "Google User"}
        
    return token_data

def get_user_credentials() -> Optional[Credentials]:
    """
    Retrieves OAuth credentials from the session, automatically refreshing if expired.
    Returns None if no user token is stored in session.
    """
    token_data = session.get(SESSION_TOKEN_KEY)
    if not token_data or not token_data.get("token"):
        return None
        
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id", Config.GOOGLE_CLIENT_ID),
        client_secret=token_data.get("client_secret", Config.GOOGLE_CLIENT_SECRET),
        scopes=token_data.get("scopes", Config.GOOGLE_OAUTH_SCOPES),
    )
    
    # Auto-refresh expired token if refresh_token is available
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update session with refreshed access token
            token_data["token"] = creds.token
            session[SESSION_TOKEN_KEY] = token_data
            session.modified = True
            logger.info("Successfully refreshed expired Google OAuth access token.")
        except Exception as e:
            logger.error(f"Failed to refresh expired OAuth token: {e}")
            session.pop(SESSION_TOKEN_KEY, None)
            return None
            
    return creds

def require_credentials() -> Credentials:
    """Returns valid user credentials or raises AuthRequiredError."""
    creds = get_user_credentials()
    if not creds or not creds.valid:
        raise AuthRequiredError("Please sign in with Google to access this service.")
    return creds

def is_authenticated() -> bool:
    """Checks whether the current session has an authenticated, valid Google token."""
    creds = get_user_credentials()
    return bool(creds and creds.valid)

def get_current_user() -> Optional[Dict[str, Any]]:
    """Returns cached user profile info if signed in."""
    if not is_authenticated():
        return None
    return session.get(SESSION_USER_KEY, {})

def clear_session_auth():
    """Logs out the user by removing tokens from session."""
    session.pop(SESSION_TOKEN_KEY, None)
    session.pop(SESSION_USER_KEY, None)
