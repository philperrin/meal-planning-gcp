"""
Integration tests for Flask REST API routes (/api/*).
"""

import json
from unittest.mock import patch

def test_index_route_unauthenticated(client):
    """When logged out, navigation tabs for History, Preferences, and Settings must not be rendered."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Meal Planning Assistant" in html
    assert "styles.css" in html
    assert "api_client.js" in html
    assert "app.js" in html
    
    # Planner tab must be present
    assert 'data-view="planner"' in html
    # History, Preferences, Settings tabs should NOT appear in desktop or mobile nav
    assert 'data-view="history"' not in html
    assert 'data-view="preferences"' not in html
    assert 'data-view="settings"' not in html

def test_index_route_authenticated(auth_client):
    """When logged in, all navigation tabs must be present."""
    response = auth_client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-view="planner"' in html
    assert 'data-view="history"' in html
    assert 'data-view="preferences"' in html
    assert 'data-view="settings"' in html
    assert "Sign Out" in html

def test_auth_status_route(client):
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "authenticated" in data
    assert data["authenticated"] is False

def test_api_load_data_unauthenticated(client):
    response = client.get("/api/data")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "db" in data
    assert "preferences" in data["db"]
    assert data["authenticated"] is False
    assert data["hasApiKey"] is True
    assert data["apiKeyStatus"]["activeKeyType"] == "shared"

def test_api_load_data_authenticated(auth_client):
    response = auth_client.get("/api/data")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["authenticated"] is True

def test_unauthenticated_meal_plan_generation(client, sample_recipes):
    """
    When logged out, generated meals must be returned in the response for observation
    but MUST NOT be saved to any database, recipeLibrary, or history.
    """
    with patch("routes.api.generate_meal_plan_ai", return_value=sample_recipes):
        payload = {
            "mealCount": 2,
            "planPreferences": "Quick dinners",
            "reusedRecipeNames": [],
            "selectedTags": ["quick"],
            "lockedIndices": [],
            "pantryIngredients": []
        }
        response = client.post("/api/meal-plan/generate", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["db"]["mealPlan"]["recipes"]) == 2
        # Recipe library should not contain unauthenticated recipes
        assert data["db"].get("recipeLibrary") == {}

        # Verify history is empty
        hist_resp = client.get("/api/recipes/history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.get_json()
        assert len(hist_data["history"]) == 0
        assert len(hist_data["favorites"]) == 0

def test_authenticated_meal_plan_generation(auth_client, sample_recipes):
    """
    When logged in, generated meals must be saved to recipeLibrary and persisted in database.
    """
    with patch("routes.api.generate_meal_plan_ai", return_value=sample_recipes):
        payload = {
            "mealCount": 2,
            "planPreferences": "Quick dinners",
            "reusedRecipeNames": [],
            "selectedTags": ["quick"],
            "lockedIndices": [],
            "pantryIngredients": []
        }
        response = auth_client.post("/api/meal-plan/generate", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["db"]["mealPlan"]["recipes"]) == 2
        assert sample_recipes[0]["name"] in data["db"]["recipeLibrary"]

        # Verify recipes appear in history
        hist_resp = auth_client.get("/api/recipes/history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.get_json()
        assert len(hist_data["history"]) == 2

def test_api_save_preferences(auth_client):
    payload = {
        "allergies": "No tree nuts",
        "dietaryPreferences": "Mediterranean focus, high olive oil",
        "dinersCount": 4,
        "defaultMealTime": "07:00 PM",
        "skipWelcomePage": True
    }
    response = auth_client.post("/api/preferences", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    prefs = data["db"]["preferences"]
    assert prefs["allergies"] == "No tree nuts"
    assert prefs["dietaryPreferences"] == "Mediterranean focus, high olive oil"
    assert prefs["dinersCount"] == 4
    assert prefs["defaultMealTime"] == "07:00 PM"
    assert prefs["skipWelcomePage"] is True

def test_api_skip_welcome_fast_toggle(auth_client):
    response = auth_client.post("/api/preferences/skip-welcome", json={"skip": True})
    assert response.status_code == 200
    assert response.get_json()["skipWelcomePage"] is True

    # Check persistence
    data_resp = auth_client.get("/api/data")
    assert data_resp.get_json()["db"]["preferences"]["skipWelcomePage"] is True

def test_api_personal_key_override_lifecycle(client):
    # Save personal key
    save_resp = client.post("/api/settings/api-key", json={"apiKey": "AIzaSyPersonal12345"})
    assert save_resp.status_code == 200
    assert save_resp.get_json()["apiKeyStatus"]["activeKeyType"] == "personal"
    assert save_resp.get_json()["apiKeyStatus"]["hasPersonalKey"] is True

    # Delete personal key
    del_resp = client.delete("/api/settings/api-key")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["apiKeyStatus"]["activeKeyType"] == "shared"
    assert del_resp.get_json()["apiKeyStatus"]["hasPersonalKey"] is False

def test_api_toggle_favorite_and_rating(auth_client, sample_recipes):
    recipe = sample_recipes[0]
    
    # 1. Favorite recipe
    fav_resp = auth_client.post("/api/recipes/favorite", json={
        "recipeName": recipe["name"],
        "isFavorite": True,
        "recipeObj": recipe
    })
    assert fav_resp.status_code == 200
    fav_data = fav_resp.get_json()
    assert fav_data["isFavorite"] is True
    assert fav_data["rating"] == 5

