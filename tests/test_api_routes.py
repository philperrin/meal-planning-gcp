"""
Integration tests for Flask REST API routes (/api/*).
"""

import json

def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Meal Planning Assistant" in html
    assert "styles.css" in html
    assert "api_client.js" in html
    assert "app.js" in html

def test_auth_status_route(client):
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "authenticated" in data
    assert data["authenticated"] is False

def test_api_load_data(client):
    response = client.get("/api/data")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "db" in data
    assert "preferences" in data["db"]
    assert data["hasApiKey"] is True
    assert data["apiKeyStatus"]["activeKeyType"] == "shared"

def test_api_save_preferences(client):
    payload = {
        "allergies": "No tree nuts",
        "dietaryPreferences": "Mediterranean focus, high olive oil",
        "dinersCount": 4,
        "defaultMealTime": "07:00 PM",
        "skipWelcomePage": True
    }
    response = client.post("/api/preferences", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    prefs = data["db"]["preferences"]
    assert prefs["allergies"] == "No tree nuts"
    assert prefs["dietaryPreferences"] == "Mediterranean focus, high olive oil"
    assert prefs["dinersCount"] == 4
    assert prefs["defaultMealTime"] == "07:00 PM"
    assert prefs["skipWelcomePage"] is True

def test_api_skip_welcome_fast_toggle(client):
    response = client.post("/api/preferences/skip-welcome", json={"skip": True})
    assert response.status_code == 200
    assert response.get_json()["skipWelcomePage"] is True

    # Check persistence
    data_resp = client.get("/api/data")
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

def test_api_toggle_favorite_and_rating(client, sample_recipes):
    recipe = sample_recipes[0]
    
    # 1. Favorite recipe
    fav_resp = client.post("/api/recipes/favorite", json={
        "recipeName": recipe["name"],
        "isFavorite": True,
        "recipeObj": recipe
    })
    assert fav_resp.status_code == 200
    fav_data = fav_resp.get_json()
    assert fav_data["isFavorite"] is True
    assert fav_data["rating"] == 5
