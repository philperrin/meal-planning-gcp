"""
Gemini AI Generation Service.
Implements the model cascade (gemini-3.6-flash -> gemini-3.5-flash -> gemini-1.5-flash),
exponential backoff, structured JSON response schema enforcement, and prompt building.
Faithfully ported from Google Apps Script Code.gs (lines 518-1062).
"""

import json
import time
import random
import logging
import requests
from typing import Dict, Any, List, Optional, Tuple

from config import Config
from core.config_keys import TAG_DIRECTIVES
from core.exceptions import GeminiError, GeminiQuotaError

logger = logging.getLogger(__name__)

RECIPE_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "description": {"type": "STRING"},
        "prepTime": {"type": "STRING", "description": "e.g., '15 mins'"},
        "cookTime": {"type": "STRING", "description": "e.g., '35 mins'"},
        "ingredients": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING", "description": "Ingredient name (e.g. russet potatoes, olive oil)"},
                    "amount": {"type": "NUMBER", "description": "Numerical quantity"},
                    "unit": {"type": "STRING", "description": "Unit of measure (e.g. lbs, oz, tbsp, cups, whole)"}
                },
                "required": ["name", "amount", "unit"]
            }
        },
        "instructions": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        }
    },
    "required": ["name", "description", "prepTime", "cookTime", "ingredients", "instructions"]
}

def build_tag_directives_text(selected_tags: Optional[List[str]]) -> str:
    """Builds prompt directives string from selected constraint tag keys."""
    if not selected_tags:
        return ""
    lines = []
    for tag in selected_tags:
        if tag in TAG_DIRECTIVES:
            lines.append(TAG_DIRECTIVES[tag])
    if not lines:
        return ""
    return "- Quick Presets Guideline (Incorporate across one or more meals in the plan):\n" + "\n".join(lines) + "\n"

def build_pantry_directive_text(pantry_ingredients: Optional[List[str]], target_count: int = 2) -> str:
    """Builds prompt directive string for prioritizing perishable on-hand/pantry ingredients."""
    if not pantry_ingredients:
        return ""
    cleaned = [str(s).strip() for s in pantry_ingredients if str(s).strip()]
    if not cleaned:
        return ""
    n = max(1, min(target_count, len(cleaned)))
    return f"- CRITICAL: You MUST prioritize using the following on-hand ingredients across the first {n} meals to prevent food waste: [{', '.join(cleaned)}]. Ensure these ingredients are explicitly incorporated and clearly listed in those recipes' ingredients lists.\n"

def call_gemini_with_retry_and_fallback(
    payload: Dict[str, Any],
    api_key: str,
    key_type: str = "shared"
) -> Dict[str, Any]:
    """
    Executes a Gemini generateContent call with automatic exponential backoff on 503/500/502/504
    and automatic fallback cascade (gemini-3.6-flash -> gemini-3.5-flash -> gemini-1.5-flash).
    """
    if not api_key:
        raise GeminiError("Gemini API key is not configured. Please supply an API key in Settings or environment.")

    models_to_try = Config.GEMINI_FALLBACK_MODELS
    last_error: Optional[Exception] = None

    for m_idx, model_name in enumerate(models_to_try):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        delay = Config.GEMINI_INITIAL_RETRY_DELAY

        for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60
                )
                status = response.status_code
                response_text = response.text

                if status == 200:
                    json_resp = response.json()
                    candidates = json_resp.get("candidates", [])
                    if not candidates or not candidates[0].get("content", {}).get("parts", []):
                        raise GeminiError("Gemini returned an empty candidate response.")
                    
                    text_content = candidates[0]["content"]["parts"][0].get("text", "")
                    try:
                        parsed_data = json.loads(text_content)
                    except json.JSONDecodeError as jde:
                        raise GeminiError(f"Failed to parse JSON response from Gemini: {jde}\nRaw: {text_content[:200]}")

                    return {
                        "modelUsed": model_name,
                        "text": text_content,
                        "data": parsed_data
                    }

                # Handle Quota / Rate Limit (429)
                if status == 429:
                    if key_type == "shared":
                        raise GeminiQuotaError("The shared starter API quota is temporarily full. Please wait a moment, or add your own free personal API key in Settings for instant dedicated access.")
                    else:
                        raise GeminiQuotaError("Your personal Gemini API rate limit or quota has been reached. Please check your Google AI Studio quota limits.")

                # Model not found / deprecated (404) -> Skip immediately to next model in cascade
                if status == 404:
                    logger.warning(f"Gemini model {model_name} returned 404 Not Found. Skipping to next model in cascade: {response_text}")
                    last_error = GeminiError(f"Gemini API model {model_name} not found (Status 404)")
                    break

                # Transient server errors: 503, 500, 502, 504
                if status in (500, 502, 503, 504):
                    logger.warning(f"Gemini API returned status {status} for model {model_name} (attempt {attempt}/{Config.GEMINI_MAX_RETRIES})")
                    last_error = GeminiError(f"Gemini API transient error (Status {status}): {response_text[:200]}", status_code=status)
                    if attempt < Config.GEMINI_MAX_RETRIES:
                        wait_time = delay + random.uniform(0, 0.5)
                        time.sleep(wait_time)
                        delay *= 2
                        continue
                    break

                # Non-retryable error (e.g. 400 Bad Request, 403 Forbidden)
                raise GeminiError(f"Gemini API error (Status {status}): {response_text[:300]}", status_code=status)

            except (GeminiQuotaError, GeminiError) as ge:
                if isinstance(ge, GeminiQuotaError) or (hasattr(ge, "status_code") and ge.status_code in (400, 403)):
                    raise ge
                last_error = ge
                if attempt < Config.GEMINI_MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
            except requests.RequestException as req_err:
                logger.warning(f"Network error calling Gemini API: {req_err}")
                last_error = GeminiError(f"Network error connecting to Gemini: {str(req_err)}")
                if attempt < Config.GEMINI_MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2

        if m_idx < len(models_to_try) - 1:
            logger.info(f"Switching to fallback model: {models_to_try[m_idx + 1]} after {model_name} failed.")

    raise last_error or GeminiError("Failed to generate response from Gemini API after cascade and retries.")

def generate_meal_plan_ai(
    remaining_count: int,
    preferences: Dict[str, Any],
    plan_preferences: str = "",
    selected_tags: Optional[List[str]] = None,
    avoid_names: Optional[List[str]] = None,
    pantry_ingredients: Optional[List[str]] = None,
    api_key: str = "",
    key_type: str = "shared"
) -> List[Dict[str, Any]]:
    """
    Generates remaining_count unique dinner recipes matching all household and meal plan constraints.
    """
    diners_count = preferences.get("dinersCount", 4)
    allergies = preferences.get("allergies", "None specified")
    dietary_prefs = preferences.get("dietaryPreferences", "None specified")
    
    # Cuisine preferences (prefer vs avoid)
    cuisine_prefs = preferences.get("cuisinePreferences", {}) or {}
    preferred_cuisines = [k for k, v in cuisine_prefs.items() if v == "prefer"]
    avoided_cuisines = [k for k, v in cuisine_prefs.items() if v == "avoid"]
    
    cuisine_constraint_text = ""
    if preferred_cuisines:
        cuisine_constraint_text += f"- Preferred Cuisines: Prioritize and feature dinner recipes inspired by the following cuisines: {', '.join(preferred_cuisines)}.\n"
    if avoided_cuisines:
        cuisine_constraint_text += f"- Avoided Cuisines: Strictly DO NOT generate any recipes, flavor profiles, or dishes associated with the following cuisines: {', '.join(avoided_cuisines)}.\n"

    avoid_text = ""
    if avoid_names:
        avoid_text = f"- Avoid Duplicating Planned Meals: The user has already selected/locked the following dishes for this meal plan: [{', '.join(avoid_names)}]. Do NOT generate duplicates or dishes with identical primary flavor profiles.\n"

    tag_directives_text = build_tag_directives_text(selected_tags)
    pantry_directive_text = build_pantry_directive_text(
        pantry_ingredients,
        target_count=min(remaining_count, 2 if len(pantry_ingredients or []) > 1 else 1)
    )

    plan_pref_text = f"- Specific Preferences / Requests for this meal plan: {plan_preferences}\n\n" if plan_preferences else "\n\n"

    prompt = (
        f"You are an acclaimed executive chef and home meal-planning specialist. "
        f"You have been professionally trained as a nutritionist and seek to provide high quality meals that contain depth of flavor in each meal. "
        f"Create a delicious dinner meal plan consisting of exactly {remaining_count} distinct dinner recipes. "
        f"All ingredient quantities must be precisely scaled to serve exactly {diners_count} diners.\n\n"

        "=== CULINARY EXCELLENCE GUIDELINES ===\n"
        "1. COMPLETE, NUTRITIONALLY BALANCED MEALS: Each recipe must represent a satisfying, complete dinner "
        "(incorporating a main protein/centerpiece, vibrant vegetables, and complementary starches or sides within the dish or as paired accompaniments).\n"
        "2. FLAVOR & TECHNIQUE: Emphasize chef-grade flavor building—seasoning in stages, aromatic bases, proper searing/caramelization, "
        "and finishing with balancing acids (citrus, vinegar) or fresh herbs.\n"
        "3. VARIED WEEKLY MENU: Across the generated meals, ensure diversity in primary proteins (e.g. alternating chicken, fish, beef, vegetarian), "
        "cooking methods (roasting, sautéing, braising, sheet-pan), and flavor profiles.\n"
        "4. ACTIONABLE, RELIABLE INSTRUCTIONS: Instructions must include specific pan types, heat levels (medium-high, gentle simmer), "
        "sensory doneness cues ('golden-brown', 'translucent'), and approximate cook times per step.\n"
        "5. CLEAN GROCERY INGREDIENTS: In the ingredients list, keep 'name' clean as a standard grocery item (e.g., 'yellow onion', 'chicken thighs') "
        "and describe preparation (diced, minced) in the recipe instructions or unit.\n\n"

        "=== CRITICAL CONSTRAINTS (STRICT ADHERENCE REQUIRED) ===\n"
        f"- ALLERGIES & ABSOLUTE EXCLUSIONS (Zero Tolerance): {allergies}. Never include these or their hidden derivatives.\n"
        f"- Dietary & Household Preferences: {dietary_prefs}\n"
        f"{cuisine_constraint_text}"
        f"{pantry_directive_text}"
        f"{avoid_text}"
        f"{tag_directives_text}"
        f"{plan_pref_text}\n"

        "Format the output strictly according to the requested JSON schema with no preamble or markdown outside the JSON."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "recipes": {
                        "type": "ARRAY",
                        "description": f"A list of {remaining_count} dinner recipes satisfying all constraints",
                        "items": RECIPE_ITEM_SCHEMA
                    }
                },
                "required": ["recipes"]
            }
        }
    }

    result = call_gemini_with_retry_and_fallback(payload, api_key=api_key, key_type=key_type)
    recipes = result["data"].get("recipes", [])
    if not recipes:
        raise GeminiError("Gemini returned an empty recipes list.")
    return recipes

def reroll_single_recipe_ai(
    target_index: int,
    existing_recipes: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    plan_preferences: str = "",
    selected_tags: Optional[List[str]] = None,
    pantry_ingredients: Optional[List[str]] = None,
    api_key: str = "",
    key_type: str = "shared"
) -> Dict[str, Any]:
    """
    Generates 1 single replacement dinner recipe, avoiding duplicates of all other meals in the plan.
    """
    diners_count = preferences.get("dinersCount", 4)
    allergies = preferences.get("allergies", "None specified")
    dietary_prefs = preferences.get("dietaryPreferences", "None specified")

    cuisine_prefs = preferences.get("cuisinePreferences", {}) or {}
    preferred_cuisines = [k for k, v in cuisine_prefs.items() if v == "prefer"]
    avoided_cuisines = [k for k, v in cuisine_prefs.items() if v == "avoid"]

    cuisine_constraint_text = ""
    if preferred_cuisines:
        cuisine_constraint_text += f"- Preferred Cuisines: Prioritize and feature dinner recipes inspired by the following cuisines: {', '.join(preferred_cuisines)}.\n"
    if avoided_cuisines:
        cuisine_constraint_text += f"- Avoided Cuisines: Strictly DO NOT generate any recipes, flavor profiles, or dishes associated with the following cuisines: {', '.join(avoided_cuisines)}.\n"

    # Collect avoid names from all existing recipes in the plan
    existing_names = [
        r.get("name") for idx, r in enumerate(existing_recipes)
        if r and r.get("name") and idx != target_index
    ]
    if target_index < len(existing_recipes) and existing_recipes[target_index].get("name"):
        existing_names.append(existing_recipes[target_index]["name"])

    avoid_text = ""
    if existing_names:
        avoid_text = f"- Avoid Duplicating Planned Meals: The user already has or wants to replace the following dishes: [{', '.join(existing_names)}]. Do NOT generate duplicates or dishes with identical primary flavor profiles.\n"

    tag_directives_text = build_tag_directives_text(selected_tags)
    pantry_directive_text = ""
    if pantry_ingredients:
        pantry_directive_text = f"- CRITICAL: Prioritize incorporating the following on-hand ingredients in this recipe to prevent food waste: [{', '.join(pantry_ingredients)}].\n"

    plan_pref_text = f"- Specific Preferences / Requests for this meal plan: {plan_preferences}\n\n" if plan_preferences else "\n\n"

    prompt = (
        f"You are an acclaimed executive chef and home meal-planning specialist. "
        f"You have been professionally trained as a nutritionist and seek to provide high quality meals that contain depth of flavor in each meal. "
        f"Create 1 delicious replacement dinner recipe. "
        f"All ingredient quantities must be precisely scaled to serve exactly {diners_count} diners.\n\n"

        "=== CULINARY EXCELLENCE GUIDELINES ===\n"
        "1. COMPLETE, NUTRITIONALLY BALANCED MEAL: The recipe must represent a satisfying, complete dinner "
        "(incorporating a main protein/centerpiece, vibrant vegetables, and complementary starches or sides within the dish or as paired accompaniments).\n"
        "2. FLAVOR & TECHNIQUE: Emphasize chef-grade flavor building—seasoning in stages, aromatic bases, proper searing/caramelization, "
        "and finishing with balancing acids (citrus, vinegar) or fresh herbs.\n"
        "3. HARMONIOUS REPLACEMENT: Ensure this dish provides a fresh flavor profile and protein distinct from the existing/avoided meals.\n"
        "4. ACTIONABLE, RELIABLE INSTRUCTIONS: Instructions must include specific pan types, heat levels (medium-high, gentle simmer), "
        "sensory doneness cues ('golden-brown', 'translucent'), and approximate cook times per step.\n"
        "5. CLEAN GROCERY INGREDIENTS: In the ingredients list, keep 'name' clean as a standard grocery item (e.g., 'yellow onion', 'chicken thighs') "
        "and describe preparation (diced, minced) in the recipe instructions or unit.\n\n"

        "=== CRITICAL CONSTRAINTS (STRICT ADHERENCE REQUIRED) ===\n"
        f"- ALLERGIES & ABSOLUTE EXCLUSIONS (Zero Tolerance): {allergies}. Never include these or their hidden derivatives.\n"
        f"- Dietary & Household Preferences: {dietary_prefs}\n"
        f"{cuisine_constraint_text}"
        f"{pantry_directive_text}"
        f"{avoid_text}"
        f"{tag_directives_text}"
        f"{plan_pref_text}\n"

        "Format the output strictly according to the requested JSON schema with no preamble or markdown outside the JSON."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RECIPE_ITEM_SCHEMA
        }
    }

    result = call_gemini_with_retry_and_fallback(payload, api_key=api_key, key_type=key_type)
    recipe = result["data"]
    if not recipe or not recipe.get("name"):
        raise GeminiError("Gemini returned an invalid replacement recipe.")
    return recipe
