"""
Unit tests for user registry tracking and alerting logic.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from core.user_registry import record_user_login, load_user_registry, save_user_registry

def test_record_new_user_login(tmp_path, monkeypatch):
    """Verifies that a first-time user login is identified as new, saved, and returns True."""
    test_json_file = tmp_path / "test_users_registry.json"
    monkeypatch.setattr("config.Config.LOCAL_USER_REGISTRY_PATH", str(test_json_file))
    monkeypatch.setattr("config.Config.USER_REGISTRY_BUCKET", "")

    user = {
        "email": "alex@example.com",
        "name": "Alex Smith"
    }

    # First login -> Should return True (new user)
    is_new = record_user_login(user)
    assert is_new is True

    # Check that file was created and contains user
    registry = load_user_registry()
    assert "alex@example.com" in registry
    assert registry["alex@example.com"]["name"] == "Alex Smith"
    assert registry["alex@example.com"]["login_count"] == 1
    assert "first_login" in registry["alex@example.com"]

    # Second login -> Should return False (returning user)
    is_new_second = record_user_login(user)
    assert is_new_second is False

    registry_after = load_user_registry()
    assert registry_after["alex@example.com"]["login_count"] == 2

def test_record_user_case_insensitivity(tmp_path, monkeypatch):
    """Verifies that email casing differences are normalized."""
    test_json_file = tmp_path / "test_users_registry.json"
    monkeypatch.setattr("config.Config.LOCAL_USER_REGISTRY_PATH", str(test_json_file))
    monkeypatch.setattr("config.Config.USER_REGISTRY_BUCKET", "")

    user1 = {"email": "Test.User@Example.COM", "name": "Test User"}
    user2 = {"email": "test.user@example.com", "name": "Test User"}

    assert record_user_login(user1) is True
    assert record_user_login(user2) is False

def test_record_empty_user_handling():
    """Verifies graceful handling of empty/invalid user profile."""
    assert record_user_login({}) is False
    assert record_user_login({"email": ""}) is False
