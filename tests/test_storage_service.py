"""
Unit tests for storage_service: schema migrations and database operations.
"""

from services.storage_service import migrate_db_schema, LocalStorageProvider, delete_recipes_from_db
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
    assert migrated["preferences"]["dinersCount"] == 4
    assert migrated["preferences"]["defaultMealTime"] == "5:30pm"
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
    assert db["preferences"]["dinersCount"] == 4
    assert db["preferences"]["allergies"] == ""
    assert db["preferences"]["dietaryPreferences"] == ""
    assert db["preferences"]["defaultMealTime"] == "5:30pm"
    
    # 2. Modify and save
    db["preferences"]["dinersCount"] = 6
    db["preferences"]["allergies"] = "Shellfish"
    provider.save_db(db)
    
    # 3. Reload and verify persistence
    reloaded = provider.load_db()
    assert reloaded["preferences"]["dinersCount"] == 6
    assert reloaded["preferences"]["allergies"] == "Shellfish"

def test_delete_recipes_from_db_and_prevent_migration_resurrection():
    db = {
        "recipeLibrary": {
            "Recipe A": {"name": "Recipe A", "docId": "doc-123"},
            "Recipe B": {"name": "Recipe B", "docId": "doc-456"}
        },
        "recipeRatings": {
            "Recipe A": {"isFavorite": True, "rating": 5},
            "Recipe B": {"isFavorite": False, "rating": 0}
        }
    }

    updated_db, doc_ids = delete_recipes_from_db(db, ["Recipe A"])
    assert "Recipe A" not in updated_db["recipeLibrary"]
    assert "Recipe A" not in updated_db["recipeRatings"]
    assert "Recipe B" in updated_db["recipeLibrary"]
    assert doc_ids == ["doc-123"]

    # Verify migration does not resurrect Recipe A
    migrated, _ = migrate_db_schema(updated_db)
    assert "Recipe A" not in migrated["recipeLibrary"]

