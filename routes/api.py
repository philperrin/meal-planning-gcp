"""
REST API Blueprint.
Maps 1:1 with all Google Apps Script functions from Code.gs.
"""

import copy
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from flask import Blueprint, request, jsonify, session

from config import Config
from core.auth import get_user_credentials, require_credentials, is_authenticated
from core.exceptions import AppError, GeminiError, GeminiQuotaError, StorageError
from services.storage_service import get_storage_provider
from services.gemini_service import generate_meal_plan_ai, reroll_single_recipe_ai
from services.calendar_service import schedule_approved_meals
from services.docs_service import create_recipe_doc

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

def get_effective_api_key() -> Tuple[str, str]:
    """
    Resolves the effective Gemini API key using the Hybrid model.
    Checks session for personal key override first; falls back to Config.GEMINI_API_KEY.
    """
    personal_key = session.get("personal_gemini_api_key", "").strip()
    if personal_key:
        return personal_key, "personal"
    
    shared_key = Config.GEMINI_API_KEY.strip()
    if shared_key:
        return shared_key, "shared"
        
    return "", "none"

@api_bp.errorhandler(AppError)
def handle_app_error(e: AppError):
    return jsonify({"success": False, "error": e.message}), e.status_code

@api_bp.errorhandler(Exception)
def handle_general_exception(e: Exception):
    logger.exception(f"Unhandled error in API route: {e}")
    return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/data", methods=["GET"])
def load_app_data():
    """Loads database contents, preferences, active plan, and API key status."""
    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    api_key, key_type = get_effective_api_key()
    personal_key = session.get("personal_gemini_api_key", "").strip()

    return jsonify({
        "success": True,
        "db": db,
        "hasApiKey": key_type != "none",
        "apiKeyStatus": {
            "hasPersonalKey": bool(personal_key),
            "hasSharedKey": bool(Config.GEMINI_API_KEY.strip()),
            "activeKeyType": key_type
        },
        "authenticated": is_authenticated()
    })

@api_bp.route("/preferences", methods=["POST"])
def save_preferences():
    """Saves updated user preferences."""
    payload = request.get_json() or {}
    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    pref_data = payload.get("preferences", payload)
    
    db["preferences"] = {
        "allergies": pref_data.get("allergies", ""),
        "dietaryPreferences": pref_data.get("dietaryPreferences", ""),
        "cuisinePreferences": pref_data.get("cuisinePreferences", {}) if isinstance(pref_data.get("cuisinePreferences"), dict) else {},
        "dinersCount": int(pref_data.get("dinersCount", 4)),
        "defaultMealTime": pref_data.get("defaultMealTime", "5:30pm"),
        "skipWelcomePage": bool(pref_data.get("skipWelcomePage", False)),
        "pantryIngredients": pref_data.get("pantryIngredients", db.get("preferences", {}).get("pantryIngredients", []))
    }

    storage.save_db(db)
    return jsonify({"success": True, "db": db})

@api_bp.route("/preferences/skip-welcome", methods=["POST"])
def set_skip_welcome():
    """Quick update for the skip welcome page preference."""
    payload = request.get_json() or {}
    skip = bool(payload.get("skip", False))
    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    if "preferences" not in db:
        db["preferences"] = {}
    db["preferences"]["skipWelcomePage"] = skip

    storage.save_db(db)
    return jsonify({"success": True, "skipWelcomePage": skip})

@api_bp.route("/settings/api-key", methods=["POST"])
def save_api_key():
    """Saves a personal Gemini API key override in the user's session."""
    payload = request.get_json() or {}
    key = payload.get("apiKey", "").strip()
    if not key:
        raise AppError("API key cannot be empty.")
        
    session["personal_gemini_api_key"] = key
    api_key, key_type = get_effective_api_key()

    return jsonify({
        "success": True,
        "apiKeyStatus": {
            "hasPersonalKey": True,
            "hasSharedKey": bool(Config.GEMINI_API_KEY.strip()),
            "activeKeyType": "personal"
        }
    })

@api_bp.route("/settings/api-key", methods=["DELETE"])
def delete_api_key():
    """Clears the personal Gemini API key override from session."""
    session.pop("personal_gemini_api_key", None)
    api_key, key_type = get_effective_api_key()

    return jsonify({
        "success": True,
        "apiKeyStatus": {
            "hasPersonalKey": False,
            "hasSharedKey": bool(Config.GEMINI_API_KEY.strip()),
            "activeKeyType": key_type
        }
    })

@api_bp.route("/meal-plan/generate", methods=["POST"])
def generate_meal_plan():
    """Generates dinner meal plan incorporating locked dishes, reused favorites, and Gemini AI."""
    payload = request.get_json() or {}
    meal_count = int(payload.get("mealCount", 4))
    plan_preferences = str(payload.get("planPreferences", "")).strip()
    reused_recipe_names = payload.get("reusedRecipeNames", []) or []
    selected_tags = payload.get("selectedTags", []) or []
    locked_indices = payload.get("lockedIndices", []) or []
    pantry_ingredients = payload.get("pantryIngredients", []) or []

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()
    prefs = db.get("preferences", {})
    recipe_library = db.get("recipeLibrary", {})
    existing_plan_recipes = (db.get("mealPlan", {}) or {}).get("recipes", []) or []

    # 1. Resolve locked recipes
    locked_map: Dict[int, Dict[str, Any]] = {}
    locked_names = []
    for idx in locked_indices:
        try:
            num_idx = int(idx)
            if 0 <= num_idx < len(existing_plan_recipes) and num_idx < meal_count:
                rec = existing_plan_recipes[num_idx]
                if rec and rec.get("name"):
                    locked_map[num_idx] = rec
                    locked_names.append(rec["name"])
        except ValueError:
            continue

    # 2. Resolve reused recipes
    resolved_reused = []
    for r_name in reused_recipe_names:
        cached = recipe_library.get(r_name)
        if cached:
            cloned = copy.deepcopy(cached)
            orig_diners = int(cloned.get("originalDiners", prefs.get("dinersCount", 4)) or 4)
            curr_diners = int(prefs.get("dinersCount", 4) or 4)
            if orig_diners != curr_diners and "ingredients" in cloned:
                for ing in cloned["ingredients"]:
                    if isinstance(ing.get("amount"), (int, float)):
                        ing["amount"] = round(ing["amount"] * curr_diners / orig_diners, 2)
            cloned["isReused"] = True
            resolved_reused.append(cloned)

    max_reused_slots = max(0, meal_count - len(locked_map))
    reused_to_include = resolved_reused[:max_reused_slots]
    remaining_count = meal_count - (len(locked_map) + len(reused_to_include))

    newly_generated: List[Dict[str, Any]] = []
    if remaining_count > 0:
        api_key, key_type = get_effective_api_key()
        if not api_key:
            raise AppError("Gemini API key is not configured. Please supply an API key in Settings.")

        avoid_names = [r["name"] for r in reused_to_include if r.get("name")]
        for name in locked_names:
            if name not in avoid_names:
                avoid_names.append(name)

        newly_generated = generate_meal_plan_ai(
            remaining_count=remaining_count,
            preferences=prefs,
            plan_preferences=plan_preferences,
            selected_tags=selected_tags,
            avoid_names=avoid_names,
            pantry_ingredients=pantry_ingredients,
            api_key=api_key,
            key_type=key_type
        )

    # 3. Merge locked recipes in place, fill empty slots with reused + newly generated
    pool = reused_to_include + newly_generated
    final_recipes: List[Dict[str, Any]] = []
    pool_idx = 0

    for i in range(meal_count):
        if i in locked_map:
            final_recipes.append(locked_map[i])
        elif pool_idx < len(pool):
            final_recipes.append(pool[pool_idx])
            pool_idx += 1

    gen_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for recipe in final_recipes:
        if recipe and recipe.get("name") and recipe["name"] not in recipe_library:
            recipe_library[recipe["name"]] = {
                "name": recipe["name"],
                "description": recipe.get("description", ""),
                "prepTime": recipe.get("prepTime", "15m"),
                "cookTime": recipe.get("cookTime", "20m"),
                "ingredients": recipe.get("ingredients", []),
                "instructions": recipe.get("instructions", []),
                "docUrl": recipe.get("docUrl", recipe.get("url", "")),
                "docId": recipe.get("docId", recipe.get("fileId", "")),
                "originalDiners": prefs.get("dinersCount", 4),
                "lastScheduledDate": recipe.get("lastScheduledDate", recipe.get("date", gen_date))
            }

    db["mealPlan"] = {
        "recipes": final_recipes,
        "approved": False,
        "selectedTags": selected_tags,
        "pantryIngredients": pantry_ingredients,
        "lockedIndices": list(locked_map.keys()),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "executionResult": None
    }
    db["recipeLibrary"] = recipe_library
    db["preferences"]["pantryIngredients"] = pantry_ingredients

    storage.save_db(db)
    return jsonify({"success": True, "db": db})

@api_bp.route("/meal-plan/reroll", methods=["POST"])
def reroll_single_recipe():
    """Rerolls a single dish in the active meal plan."""
    payload = request.get_json() or {}
    target_index = int(payload.get("targetIndex", 0))
    existing_recipes = payload.get("existingRecipes", []) or []
    plan_preferences = str(payload.get("planPreferences", "")).strip()
    selected_tags = payload.get("selectedTags", []) or []
    pantry_ingredients = payload.get("pantryIngredients", []) or []

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()
    prefs = db.get("preferences", {})

    api_key, key_type = get_effective_api_key()
    if not api_key:
        raise AppError("Gemini API key is not configured. Please supply an API key in Settings.")

    new_recipe = reroll_single_recipe_ai(
        target_index=target_index,
        existing_recipes=existing_recipes,
        preferences=prefs,
        plan_preferences=plan_preferences,
        selected_tags=selected_tags,
        pantry_ingredients=pantry_ingredients,
        api_key=api_key,
        key_type=key_type
    )

    if not db.get("mealPlan"):
        db["mealPlan"] = {"recipes": [], "approved": False, "generatedAt": datetime.now(timezone.utc).isoformat()}
    if "recipes" not in db["mealPlan"]:
        db["mealPlan"]["recipes"] = []

    plan_recipes = db["mealPlan"]["recipes"]
    if target_index < len(plan_recipes):
        plan_recipes[target_index] = new_recipe
    else:
        plan_recipes.append(new_recipe)

    if "recipeLibrary" not in db:
        db["recipeLibrary"] = {}
    db["recipeLibrary"][new_recipe["name"]] = {
        "name": new_recipe["name"],
        "description": new_recipe.get("description", ""),
        "prepTime": new_recipe.get("prepTime", "15m"),
        "cookTime": new_recipe.get("cookTime", "20m"),
        "ingredients": new_recipe.get("ingredients", []),
        "instructions": new_recipe.get("instructions", []),
        "docUrl": "",
        "docId": "",
        "originalDiners": prefs.get("dinersCount", 4),
        "lastScheduledDate": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }

    storage.save_db(db)
    return jsonify({
        "success": True,
        "newRecipe": new_recipe,
        "targetIndex": target_index,
        "db": db
    })

@api_bp.route("/meal-plan/active", methods=["PUT"])
def save_active_meal_plan():
    """Saves reordered or edited recipes array in active plan."""
    payload = request.get_json() or {}
    recipes_list = payload.get("recipes", [])
    if not isinstance(recipes_list, list):
        raise AppError("Invalid recipes list format.")

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    if not db.get("mealPlan"):
        db["mealPlan"] = {"generatedAt": datetime.now(timezone.utc).isoformat(), "approved": False, "recipes": []}

    db["mealPlan"]["recipes"] = recipes_list

    if "recipeLibrary" not in db:
        db["recipeLibrary"] = {}
    for r in recipes_list:
        if r and r.get("name") and r["name"] not in db["recipeLibrary"]:
            db["recipeLibrary"][r["name"]] = {
                "name": r["name"],
                "description": r.get("description", ""),
                "prepTime": r.get("prepTime", "15m"),
                "cookTime": r.get("cookTime", "20m"),
                "ingredients": r.get("ingredients", []),
                "instructions": r.get("instructions", []),
                "docUrl": r.get("docUrl", r.get("url", "")),
                "docId": r.get("docId", r.get("fileId", "")),
                "originalDiners": db.get("preferences", {}).get("dinersCount", 4),
                "lastScheduledDate": r.get("lastScheduledDate", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            }

    storage.save_db(db)
    return jsonify({"success": True, "db": db})

@api_bp.route("/meal-plan/approve", methods=["POST"])
def approve_meal_plan():
    """Executes Calendar scheduling and grocery list generation for approved plan."""
    payload = request.get_json() or {}
    approved_meals = payload.get("approvedMealsWithDates", [])
    if not approved_meals:
        raise AppError("Please approve at least one recipe.")

    creds = require_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    meal_plan = db.get("mealPlan")
    if not meal_plan or not meal_plan.get("recipes"):
        raise AppError("No active meal plan found to approve.")

    exec_result = schedule_approved_meals(
        approved_meals_with_dates=approved_meals,
        all_recipes=meal_plan["recipes"],
        preferences=db.get("preferences", {}),
        credentials=creds
    )

    library = db.get("recipeLibrary", {})
    for item in approved_meals:
        name = item.get("name")
        date_val = item.get("date")
        if name in library:
            library[name]["lastScheduledDate"] = date_val

    db["mealPlan"]["approved"] = True
    db["mealPlan"]["executionResult"] = exec_result
    db["mealPlan"]["shoppingList"] = exec_result.get("shoppingList", [])

    storage.save_db(db)
    return jsonify({"success": True, "db": db})

@api_bp.route("/recipes/create-doc", methods=["POST"])
def create_doc_endpoint():
    """Generates an on-demand Google Doc for a recipe in the user's Drive."""
    payload = request.get_json() or {}
    recipe_name = str(payload.get("recipeName", "")).strip()
    if not recipe_name:
        raise AppError("Recipe name is required.")

    creds = require_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    library = db.get("recipeLibrary", {})
    recipe = library.get(recipe_name)
    if not recipe:
        raise AppError(f"Recipe '{recipe_name}' not found in library.")

    diners = db.get("preferences", {}).get("dinersCount", 4)
    doc_result = create_recipe_doc(recipe_name, recipe, diners, creds)

    recipe["docUrl"] = doc_result["docUrl"]
    recipe["docId"] = doc_result["docId"]
    library[recipe_name] = recipe
    db["recipeLibrary"] = library

    storage.save_db(db)
    return jsonify(doc_result)

@api_bp.route("/recipes/history", methods=["GET"])
def get_recipe_history():
    """Retrieves up to 50 scheduled recipes and 50 top-rated favorites."""
    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    ratings_map = db.get("recipeRatings", {}) or {}
    library = db.get("recipeLibrary", {}) or {}

    all_recipes = []
    for r_name, item in library.items():
        if not isinstance(item, dict):
            continue
        rating_info = ratings_map.get(r_name, {})
        is_fav = bool(rating_info.get("isFavorite") or (rating_info.get("rating", 0) > 0))
        r_rating = 5 if is_fav else rating_info.get("rating", 0)

        sched_ts = 0
        last_sched = item.get("lastScheduledDate")
        if last_sched:
            try:
                parts = [int(p) for p in str(last_sched).split("-")]
                sched_ts = datetime(parts[0], parts[1], parts[2]).timestamp()
            except Exception:
                pass

        all_recipes.append({
            "name": item.get("name", r_name),
            "date": item.get("lastScheduledDate", "Previously Planned"),
            "description": item.get("description", ""),
            "prepTime": item.get("prepTime", ""),
            "cookTime": item.get("cookTime", ""),
            "url": item.get("docUrl", ""),
            "docUrl": item.get("docUrl", ""),
            "fileId": item.get("docId", ""),
            "isFavorite": is_fav,
            "rating": r_rating,
            "scheduledTime": sched_ts
        })

    history_list = sorted(all_recipes, key=lambda x: x["scheduledTime"], reverse=True)
    favorites_list = [r for r in all_recipes if r["isFavorite"] or r["rating"] > 0]
    favorites_list = sorted(favorites_list, key=lambda x: (x["rating"], x["scheduledTime"]), reverse=True)

    return jsonify({
        "success": True,
        "history": history_list[:50],
        "favorites": favorites_list[:50],
        "ratings": ratings_map,
        "library": library
    })

@api_bp.route("/recipes/favorite", methods=["POST"])
def toggle_favorite():
    """Toggles bookmark status and caches structured recipe in library."""
    payload = request.get_json() or {}
    recipe_name = str(payload.get("recipeName", "")).strip()
    if not recipe_name:
        raise AppError("Recipe name is required.")
    is_favorite = bool(payload.get("isFavorite", False))
    recipe_obj = payload.get("recipeObj")

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    if "recipeRatings" not in db:
        db["recipeRatings"] = {}
    if "recipeLibrary" not in db:
        db["recipeLibrary"] = {}

    db["recipeRatings"][recipe_name] = {
        "isFavorite": is_favorite,
        "rating": 5 if is_favorite else 0,
        "favoritedAt": datetime.now(timezone.utc).isoformat()
    }

    if recipe_obj and isinstance(recipe_obj, dict):
        db["recipeLibrary"][recipe_name] = {
            "name": recipe_obj.get("name", recipe_name),
            "description": recipe_obj.get("description", ""),
            "prepTime": recipe_obj.get("prepTime", "20 mins"),
            "cookTime": recipe_obj.get("cookTime", "30 mins"),
            "ingredients": recipe_obj.get("ingredients", []),
            "instructions": recipe_obj.get("instructions", []),
            "docUrl": recipe_obj.get("docUrl", ""),
            "docId": recipe_obj.get("docId", ""),
            "originalDiners": int(recipe_obj.get("originalDiners", db.get("preferences", {}).get("dinersCount", 4)) or 4),
            "dateAdded": datetime.now(timezone.utc).isoformat()
        }

    storage.save_db(db)
    return jsonify({
        "success": True,
        "isFavorite": is_favorite,
        "rating": 5 if is_favorite else 0,
        "recipeRatings": db["recipeRatings"],
        "recipeLibrary": db["recipeLibrary"]
    })

@api_bp.route("/recipes/rating", methods=["POST"])
def set_rating():
    """Sets numeric star rating (0-5) for a recipe."""
    payload = request.get_json() or {}
    recipe_name = str(payload.get("recipeName", "")).strip()
    if not recipe_name:
        raise AppError("Recipe name is required.")
    try:
        rating = max(0, min(5, int(payload.get("rating", 0))))
    except ValueError:
        rating = 0
    is_favorite = rating > 0

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    if "recipeRatings" not in db:
        db["recipeRatings"] = {}

    db["recipeRatings"][recipe_name] = {
        "isFavorite": is_favorite,
        "rating": rating,
        "ratedAt": datetime.now(timezone.utc).isoformat(),
        "favoritedAt": datetime.now(timezone.utc).isoformat() if is_favorite else None
    }

    storage.save_db(db)
    return jsonify({
        "success": True,
        "rating": rating,
        "isFavorite": is_favorite,
        "recipeRatings": db["recipeRatings"]
    })

@api_bp.route("/shopping/sync", methods=["POST"])
def sync_shopping_checklist():
    """Synchronizes in-store shopping checklist items and custom additions."""
    payload = request.get_json() or {}
    checked_items = payload.get("checkedItems", [])
    custom_items = payload.get("customItems", [])

    creds = get_user_credentials()
    storage = get_storage_provider(creds)
    db = storage.load_db()

    if "mealPlan" not in db or not isinstance(db["mealPlan"], dict):
        db["mealPlan"] = {}

    if isinstance(checked_items, list):
        db["mealPlan"]["checkedItems"] = checked_items
    if isinstance(custom_items, list):
        db["mealPlan"]["customItems"] = custom_items

    storage.save_db(db)
    return jsonify({
        "success": True,
        "timestamp": db.get("lastUpdated"),
        "checkedCount": len(checked_items),
        "customCount": len(custom_items)
    })
