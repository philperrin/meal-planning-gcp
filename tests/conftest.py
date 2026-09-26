"""
Pytest fixtures and test environment setup.
"""

import os
import tempfile
import pytest
from pathlib import Path

from app import create_app
from config import Config
from services.storage_service import LocalStorageProvider
from core.config_keys import get_default_db

@pytest.fixture
def temp_db_path(tmp_path):
    """Provides a temporary path for isolated local JSON DB tests."""
    db_file = tmp_path / "test_db.json"
    return str(db_file)

@pytest.fixture
def app(temp_db_path, monkeypatch):
    """Configures a Flask test application with an isolated local DB."""
    monkeypatch.setattr(Config, "STORAGE_MODE", "local")
    monkeypatch.setattr(Config, "LOCAL_DB_PATH", temp_db_path)
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "test-mock-key")
    monkeypatch.setattr(Config, "SECRET_KEY", "test-secret-key")

    test_app = create_app()
    test_app.config["TESTING"] = True
    return test_app

@pytest.fixture
def client(app):
    """Provides a test client for simulating HTTP requests."""
    return app.test_client()

@pytest.fixture
def sample_recipes():
    """Provides realistic sample recipe data matching Gemini schema."""
    return [
        {
            "name": "Lemon Herb Grilled Chicken",
            "description": "Zesty, tender chicken breast seasoned with fresh rosemary and lemon.",
            "prepTime": "15 mins",
            "cookTime": "20 mins",
            "ingredients": [
                {"name": "chicken breast", "amount": 1.5, "unit": "lbs"},
                {"name": "olive oil", "amount": 2, "unit": "tbsp"},
                {"name": "lemon", "amount": 1, "unit": "whole"},
                {"name": "fresh rosemary", "amount": 1, "unit": "tbsp"},
                {"name": "kosher salt", "amount": 1, "unit": "tsp"},
                {"name": "black pepper", "amount": 0.5, "unit": "tsp"}
            ],
            "instructions": [
                "Marinate chicken in olive oil, lemon juice, and herbs.",
                "Grill on medium-high heat for 6-8 minutes per side.",
                "Rest for 5 minutes before slicing."
            ]
        },
        {
            "name": "Creamy Tomato Basil Penne",
            "description": "Rich comfort pasta tossed with crushed tomatoes, heavy cream, and fresh basil.",
            "prepTime": "10 mins",
            "cookTime": "15 mins",
            "ingredients": [
                {"name": "penne pasta", "amount": 1, "unit": "lbs"},
                {"name": "crushed tomato", "amount": 1, "unit": "can"},
                {"name": "heavy cream", "amount": 0.5, "unit": "cups"},
                {"name": "parmesan cheese", "amount": 0.5, "unit": "cups"},
                {"name": "garlic", "amount": 3, "unit": "cloves"},
                {"name": "fresh basil", "amount": 0.25, "unit": "cups"},
                {"name": "olive oil", "amount": 1, "unit": "tbsp"}
            ],
            "instructions": [
                "Boil penne in salted water until al dente.",
                "Saute garlic in olive oil, stir in tomatoes and cream.",
                "Toss pasta in sauce and garnish with parmesan and basil."
            ]
        }
    ]
