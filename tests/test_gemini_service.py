"""
Unit tests for gemini_service: prompt formatting, constraint directives, and retry configuration.
"""

from services.gemini_service import (
    build_tag_directives_text,
    build_pantry_directive_text,
)

def test_build_tag_directives_text():
    tags = ["quick", "one_pot"]
    text = build_tag_directives_text(tags)
    assert "Speed & Prep: Ensure all recipes require under 30 minutes" in text
    assert "Minimal Cleanup: Prioritize single-pot" in text

def test_build_tag_directives_empty():
    assert build_tag_directives_text([]) == ""
    assert build_tag_directives_text(None) == ""

def test_build_pantry_directive_text():
    pantry = ["kale", "mushrooms", "cream cheese"]
    text = build_pantry_directive_text(pantry, target_count=2)
    assert "CRITICAL: You MUST prioritize using the following on-hand ingredients" in text
    assert "kale, mushrooms, cream cheese" in text
    assert "first 2 meals" in text

def test_build_pantry_directive_empty():
    assert build_pantry_directive_text([]) == ""
    assert build_pantry_directive_text(None) == ""
