"""
Shopping list service for ingredient categorization and consolidation.
Faithfully ported from Google Apps Script Code.gs (lines 1092-1201).
"""

import re
from typing import List, Dict, Any
from core.config_keys import AISLE_CATEGORIES

# Precompiled regex patterns for performance and precision
RE_PANTRY_SAUCES = re.compile(
    r"broth|stock|bouillon|olive oil|vegetable oil|sesame oil|canola oil|cooking spray|"
    r"vinegar|soy sauce|tamari|worcestershire|fish sauce|hot sauce|sriracha|salsa|"
    r"tomato sauce|tomato paste|marinara|canned|beans|diced tomato|crushed tomato|"
    r"coconut milk|peanut butter|honey|maple syrup|mayo|mustard|ketchup|dressing",
    re.IGNORECASE
)

RE_SPICES_BAKING = re.compile(
    r"powder|seasoning|\brub\b|extract|sugar|flour|cornstarch|baking|cocoa|yeast|"
    r"cinnamon|nutmeg|paprika|cumin|turmeric|coriander|curry powder|cardamom|cayenne|"
    r"allspice|vanilla|chocolate chip|red pepper flake|chili flake",
    re.IGNORECASE
)

RE_SALT_PEPPER = re.compile(
    r"\bsalt\b|\bpepper\b|\bpeppercorn\b|\bpeppercorns\b|\bkosher salt\b|\bsea salt\b|\bblack pepper\b",
    re.IGNORECASE
)

RE_PEPPER_VEGGIES = re.compile(
    r"bell pepper|chili pepper|jalapeno|poblano|serrano|sweet pepper|banana pepper",
    re.IGNORECASE
)

RE_MEAT_SEAFOOD = re.compile(
    r"chicken|beef|steak|pork|turkey|duck|lamb|veal|bacon|pancetta|prosciutto|sausage|"
    r"chorizo|\bham\b|ribeye|sirloin|ground beef|ground turkey|ground pork|salmon|\btuna\b|"
    r"shrimp|prawn|fish|\bcod\b|tilapia|halibut|mahi|trout|crab|lobster|scallop|clam|"
    r"mussel|calamari|squid|anchov|meat",
    re.IGNORECASE
)

RE_DAIRY = re.compile(
    r"milk|butter|cheese|cheddar|mozzarella|parmesan|parmigiano|ricotta|feta|gouda|swiss|"
    r"provolone|brie|pecorino|yogurt|cream|sour cream|half and half|half & half|egg|eggs|"
    r"egg white|egg yolk|tofu|tempeh|ghee|margarine|cream cheese|cottage cheese|mascarpone|queso",
    re.IGNORECASE
)

RE_PRODUCE = re.compile(
    r"garlic|onion|shallot|leek|scallion|ginger|tomato|potato|potatoes|sweet potato|lettuce|"
    r"spinach|kale|arugula|cabbage|bok choy|chard|celery|carrot|bell pepper|jalapeno|chili|"
    r"poblano|serrano|avocado|cucumber|zucchini|squash|broccoli|cauliflower|asparagus|mushroom|"
    r"green bean|\bpea\b|\bpeas\b|snap pea|snow pea|eggplant|\bcorn\b|radish|beet|lemon|lime|"
    r"orange|apple|banana|berry|berries|strawberry|blueberry|raspberry|blackberry|mango|"
    r"pineapple|grape|peach|pear|melon|watermelon|cilantro|parsley|basil|rosemary|thyme|"
    r"mint|dill|\bsage\b|tarragon|lemongrass|sprout|herb",
    re.IGNORECASE
)

RE_GRAINS_PANTRY = re.compile(
    r"pasta|spaghetti|penne|noodle|rice|quinoa|oat|bread|tortilla|pita|cracker|panko|"
    r"breadcrumb|chip|olive|caper|\bnut\b|\bnuts\b|almond|walnut|peanut|cashew|pecan|"
    r"pine nut|seed|sunflower|sesame",
    re.IGNORECASE
)

def categorize_ingredient(raw_name: str) -> str:
    """
    Categorizes an ingredient by grocery aisle / store department.
    Follows the 5 distinct categories defined in Apps Script.
    """
    name = (raw_name or "").lower().strip()
    if not name:
        return "🥫 Pantry & Canned"

    # 1. Broths, Stocks, Oils, Sauces, Vinegars, Canned Goods -> Pantry & Canned
    if RE_PANTRY_SAUCES.search(name):
        return "🥫 Pantry & Canned"

    # 2. Spices, Powders, Seasonings, Baking
    if RE_SPICES_BAKING.search(name):
        return "🧂 Spices & Baking"
    if RE_SALT_PEPPER.search(name) and not RE_PEPPER_VEGGIES.search(name):
        return "🧂 Spices & Baking"

    # 3. Meat & Seafood
    if RE_MEAT_SEAFOOD.search(name):
        return "🥩 Meat & Seafood"

    # 4. Dairy & Refrigerated (and plant-based dairy substitutes)
    if RE_DAIRY.search(name):
        return "🧀 Dairy & Refrigerated"

    # 5. Fresh Produce
    if RE_PRODUCE.search(name):
        return "🥬 Produce"

    # 6. Grains, Pasta, Bread, Canned & Pantry fallback
    if RE_GRAINS_PANTRY.search(name):
        return "🥫 Pantry & Canned"

    # Default fallback
    return "🥫 Pantry & Canned"

def consolidate_shopping_list(recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parses and deduplicates ingredients across all recipes, merging amounts
    with matching units and categorizing each into store departments.
    """
    raw_list: Dict[str, List[Dict[str, Any]]] = {}

    for recipe in recipes:
        if not recipe or "ingredients" not in recipe:
            continue
        for ing in recipe.get("ingredients", []):
            name = (ing.get("name") or "").lower().strip()
            if not name:
                continue
            try:
                amount = float(ing.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amount = 0.0
            unit = (ing.get("unit") or "").lower().strip()

            if name not in raw_list:
                raw_list[name] = []
            raw_list[name].append({"amount": amount, "unit": unit})

    consolidated = []
    for name, items in raw_list.items():
        merged: List[Dict[str, Any]] = []
        for item in items:
            found = False
            for m in merged:
                if m["unit"] == item["unit"]:
                    m["amount"] = round(m["amount"] + item["amount"], 2)
                    found = True
                    break
            if not found:
                merged.append({"amount": round(item["amount"], 2), "unit": item["unit"]})

        category = categorize_ingredient(name)
        consolidated.append({
            "name": name,
            "category": category,
            "amounts": merged
        })

    # Sort alphabetically by ingredient name
    consolidated.sort(key=lambda x: x["name"])
    return consolidated
