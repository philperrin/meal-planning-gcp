"""
Shared constants, aisle categorization definitions, and prompt directive templates.
Faithfully ported from Google Apps Script Code.gs and JavaScript.html.
"""

from datetime import datetime, timezone

AISLE_CATEGORIES = [
    "🥬 Produce",
    "🥩 Meat & Seafood",
    "🧀 Dairy & Refrigerated",
    "🥫 Pantry & Canned",
    "🧂 Spices & Baking",
]

TAG_DIRECTIVES = {
    "quick": "- Speed & Prep: Ensure all recipes require under 30 minutes of total active prep and cooking time combined.",
    "one_pot": "- Minimal Cleanup: Prioritize single-pot, single-skillet, or sheet-pan meals requiring minimal cookware and easy cleanup.",
    "kid_friendly": "- Family & Kids: Focus on mild, approachable, kid-approved flavor profiles with familiar textures and no overly pungent/spicy seasonings.",
    "slow_cooker": "- Hands-Off Cooking: Prioritize slow-cooker (Crock-Pot), multi-cooker, or Instant Pot recipes suitable for hands-off cooking.",
    "high_veggie": "- Fresh & Light: Emphasize vegetable-forward, nutrient-dense, lighter dinners with vibrant seasonal produce.",
    "comfort": "- Comfort Food: Feature hearty, satisfying, warm comfort food classics (e.g. casseroles, bakes, comforting pasta dishes).",
}

CUISINES = [
    {"name": "American / Classic Comfort", "icon": "🍔"},
    {"name": "Chinese", "icon": "🥡"},
    {"name": "Indian", "icon": "🍛"},
    {"name": "Italian", "icon": "🍝"},
    {"name": "Korean", "icon": "🍲"},
    {"name": "Mediterranean / Greek", "icon": "🫒"},
    {"name": "Mexican", "icon": "🌮"},
    {"name": "Middle Eastern / Levantine", "icon": "🧆"},
    {"name": "Tex-Mex / Southwestern", "icon": "🥑"},
    {"name": "Thai", "icon": "🍜"},
    {"name": "Vegan", "icon": "🌱"},
    {"name": "Vegetarian", "icon": "🥗"},
]

def get_default_db():
    """Generates the initial default database schema matching Apps Script."""
    return {
        "preferences": {
            "allergies": "",
            "dietaryPreferences": "",
            "cuisinePreferences": {},
            "dinersCount": 4,
            "defaultMealTime": "5:30pm",
            "skipWelcomePage": False,
            "pantryIngredients": [],
        },
        "mealPlan": None,
        "recipeRatings": {},
        "recipeLibrary": {},
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }
