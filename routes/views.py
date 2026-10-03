"""
View routes and OAuth 2.0 endpoint handlers.
"""

import logging
from flask import Blueprint, render_template, redirect, request, url_for, session, jsonify

from core.auth import (
    get_authorization_url,
    exchange_code_for_tokens,
    clear_session_auth,
    is_authenticated,
    get_current_user,
)
from config import Config

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)

@views_bp.route("/")
def index():
    """Serves the Single Page Application."""
    user = get_current_user()
    authenticated = is_authenticated()
    return render_template(
        "index.html",
        authenticated=authenticated,
        user=user,
        project_id=Config.PROJECT_ID,
    )

@views_bp.route("/auth/login")
def auth_login():
    """Initiates Google OAuth 2.0 login flow."""
    auth_url, state, code_verifier = get_authorization_url()
    session["oauth_state"] = state
    if code_verifier:
        session["code_verifier"] = code_verifier
    session.modified = True
    return redirect(auth_url)

@views_bp.route("/auth/callback")
def auth_callback():
    """Handles the OAuth 2.0 redirect callback from Google."""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        error_desc = request.args.get("error_description", error)
        logger.error(f"Google OAuth provider returned error: {error} - {error_desc}")
        return redirect(url_for("views.index", error="oauth_denied", details=error_desc))

    if not code:
        logger.error("OAuth callback missing code parameter.")
        return redirect(url_for("views.index", error="oauth_missing_code"))

    code_verifier = session.pop("code_verifier", None)
    session.pop("oauth_state", None)

    try:
        exchange_code_for_tokens(code, state=state, code_verifier=code_verifier)
        logger.info("Google OAuth 2.0 authorization completed successfully.")
        return redirect(url_for("views.index", logged_in="true"))
    except Exception as e:
        logger.error(f"OAuth token exchange error: {e}", exc_info=True)
        return redirect(url_for("views.index", error="oauth_failed", details=str(e)))

@views_bp.route("/auth/logout")
def auth_logout():
    """Clears user session and logs out."""
    clear_session_auth()
    return redirect(url_for("views.index"))

@views_bp.route("/auth/status")
def auth_status():
    """Returns current authentication status."""
    return jsonify({
        "authenticated": is_authenticated(),
        "user": get_current_user(),
    })

@views_bp.route("/palette-tester")
def palette_tester():
    """Serves the static color palette testing and live customization studio."""
    return render_template("palette_tester.html")

