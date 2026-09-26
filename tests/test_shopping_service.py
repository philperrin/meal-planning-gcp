"""
Unit tests for shopping_service: aisle categorization and ingredient consolidation.
"""

from services.shopping_service import categorize_ingredient, consolidate_shopping_list

def test_categorize_ingredient_produce():
    assert categorize_ingredient("garlic") == "🥬 Produce"
    assert categorize_ingredient("baby spinach") == "🥬 Produce"
    assert categorize_ingredient("fresh basil") == "🥬 Produce"
    assert categorize_ingredient("bell pepper") == "🥬 Produce"
    assert categorize_ingredient("lemon") == "🥬 Produce"

def test_categorize_ingredient_meat_seafood():
    assert categorize_ingredient("boneless skinless chicken breast") == "🥩 Meat & Seafood"
    assert categorize_ingredient("atlantic salmon fillet") == "🥩 Meat & Seafood"
    assert categorize_ingredient("ground beef") == "🥩 Meat & Seafood"
    assert categorize_ingredient("shrimp") == "🥩 Meat & Seafood"

def test_categorize_ingredient_dairy():
    assert categorize_ingredient("unsalted butter") == "🧀 Dairy & Refrigerated"
    assert categorize_ingredient("whole milk") == "🧀 Dairy & Refrigerated"
    assert categorize_ingredient("grated parmesan cheese") == "🧀 Dairy & Refrigerated"
    assert categorize_ingredient("large eggs") == "🧀 Dairy & Refrigerated"

def test_categorize_ingredient_spices_baking():
    assert categorize_ingredient("ground cumin") == "🧂 Spices & Baking"
    assert categorize_ingredient("kosher salt") == "🧂 Spices & Baking"
    assert categorize_ingredient("black pepper") == "🧂 Spices & Baking"
    assert categorize_ingredient("baking powder") == "🧂 Spices & Baking"
    assert categorize_ingredient("cinnamon") == "🧂 Spices & Baking"

def test_categorize_ingredient_pantry_canned():
    assert categorize_ingredient("extra virgin olive oil") == "🥫 Pantry & Canned"
    assert categorize_ingredient("chicken broth") == "🥫 Pantry & Canned"
    assert categorize_ingredient("diced tomatoes") == "🥫 Pantry & Canned"
    assert categorize_ingredient("soy sauce") == "🥫 Pantry & Canned"
    assert categorize_ingredient("penne pasta") == "🥫 Pantry & Canned"

def test_consolidate_shopping_list(sample_recipes):
    consolidated = consolidate_shopping_list(sample_recipes)

    # Check alphabetical ordering
    names = [item["name"] for item in consolidated]
    assert names == sorted(names)

    # Check olive oil consolidation: 2 tbsp in chicken + 1 tbsp in penne = 3 tbsp
    olive_oil_entry = next((item for item in consolidated if item["name"] == "olive oil"), None)
    assert olive_oil_entry is not None
    assert olive_oil_entry["category"] == "🥫 Pantry & Canned"
    assert len(olive_oil_entry["amounts"]) == 1
    assert olive_oil_entry["amounts"][0]["amount"] == 3.0
    assert olive_oil_entry["amounts"][0]["unit"] == "tbsp"

    # Check chicken breast category
    chicken_entry = next((item for item in consolidated if item["name"] == "chicken breast"), None)
    assert chicken_entry is not None
    assert chicken_entry["category"] == "🥩 Meat & Seafood"
