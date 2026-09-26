"""
Unit tests for storage_service: schema migrations and database operations.
"""

from services.storage_service import migrate_db_schema, LocalStorageProvider
from core.config_keys import get_default_db

def test_migrate_db_schema_restrictions_to_dietary():
    legacy_db = {
        "preferences": {
            "restrictions": "No red meat, low sodium",
            "allergies": "Peanuts"
        }
    }
    migrated, updated = migrate_db_schema(legacy_db)
    assert updated is True
    assert "restrictions" not in migrated["preferences"]
    assert migrated["preferences"]["dietaryPreferences"] == "No red meat, low sodium"
    assert migrated["preferences"]["dinersCount"] == 2
    assert migrated["preferences"]["defaultMealTime"] == "06:00 PM"
    assert migrated["preferences"]["skipWelcomePage"] is False

def test_migrate_recipe_library_from_array():
    legacy_db = {
        "recipeLibrary": [
            {"name": "Tacos", "prepTime": "10m"},
            {"name": "Burritos", "prepTime": "15m"}
        ]
    }
    migrated, updated = migrate_db_schema(legacy_db)
    assert updated is True
    assert isinstance(migrated["recipeLibrary"], dict)
    assert "Tacos" in migrated["recipeLibrary"]
    assert migrated["recipeLibrary"]["Tacos"]["prepTime"] == "10m"
    assert "Burritos" in migrated["recipeLibrary"]

def test_migrate_auto_ingest_from_active_meal_plan():
    legacy_db = {
        "mealPlan": {
            "recipes": [
                {"name": "Pan-Seared Salmon", "prepTime": "10m", "cookTime": "15m"}
            ]
        },
        "recipeLibrary": {}
    }
    migrated, updated = migrate_db_schema(legacy_db)
    assert updated is True
    assert "Pan-Seared Salmon" in migrated["recipeLibrary"]
    assert migrated["recipeLibrary"]["Pan-Seared Salmon"]["prepTime"] == "10m"

def test_local_storage_provider_lifecycle(temp_db_path):
    provider = LocalStorageProvider(temp_db_path)
    
    # 1. Load from non-existent file should create default DB
    db = provider.load_db()
    assert "preferences" in db
    assert db["preferences"]["dinersCount"] == 2
    
    # 2. Modify and save
    db["preferences"]["dinersCount"] = 4
    db["preferences"]["allergies"] = "Shellfish"
    provider.save_db(db)
    
    # 3. Reload and verify persistence
    reloaded = provider.load_db()
    assert reloaded["preferences"]["dinersCount"] == 4
    assert reloaded["preferences"]["allergies"] == "Shellfish"
