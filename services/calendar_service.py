"""
Google Calendar Service.
Schedules dinner events with complete embedded ingredients, cooking steps, and prep times,
and generates the morning '🛒 Groceries' checklist event.
Faithfully ported from Google Apps Script Code.gs (lines 1064-1090 and 1269-1375).
"""

import re
import logging
from datetime import datetime, time, timedelta, timezone
from typing import List, Dict, Any, Tuple
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from core.config_keys import AISLE_CATEGORIES
from services.shopping_service import consolidate_shopping_list
from core.exceptions import AppError

logger = logging.getLogger(__name__)

def parse_time_str(time_str: str) -> Tuple[int, int]:
    """
    Parses time string supporting AM/PM formats as well as 24-hour.
    Defaults to 17:30 (5:30 PM).
    """
    default_hours, default_minutes = 17, 30
    if not time_str:
        return default_hours, default_minutes

    clean_str = time_str.strip().upper()
    is_pm = "PM" in clean_str
    is_am = "AM" in clean_str

    clean_time = re.sub(r"[AP]M", "", clean_str).strip()
    parts = clean_time.split(":")

    if len(parts) >= 2:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            if is_pm and hours < 12:
                hours += 12
            elif is_am and hours == 12:
                hours = 0
            return hours, minutes
        except ValueError:
            pass

    return default_hours, default_minutes

def schedule_approved_meals(
    approved_meals_with_dates: List[Dict[str, str]],
    all_recipes: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    credentials: Credentials
) -> Dict[str, Any]:
    """
    Schedules individual dinner events on user's primary Google Calendar and adds
    the aisle-categorized '🛒 Groceries' event on the morning of the earliest meal.
    """
    if not credentials:
        raise AppError("Google OAuth credentials are required to schedule calendar events.")

    cal_service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    diners_count = preferences.get("dinersCount", 4)
    default_meal_time = preferences.get("defaultMealTime", "5:30pm")
    hours, minutes = parse_time_str(default_meal_time)

    approved_map = {item["name"]: item["date"] for item in approved_meals_with_dates if "name" in item and "date" in item}
    selected_recipes: List[Dict[str, Any]] = []

    for r in all_recipes:
        name = r.get("name")
        if name in approved_map:
            selected_recipes.append({
                "recipe": r,
                "dateVal": approved_map[name]
            })

    if not selected_recipes:
        raise AppError("Please approve at least one recipe.")

    calendar_events_created = 0

    # 1. Schedule Dinner Events
    for item in selected_recipes:
        recipe = item["recipe"]
        date_val = item["dateVal"]

        try:
            date_parts = [int(p) for p in date_val.split("-")]
            start_dt = datetime(date_parts[0], date_parts[1], date_parts[2], hours, minutes, 0)
            end_dt = start_dt + timedelta(hours=1)
        except Exception as e:
            logger.warning(f"Invalid date format '{date_val}': {e}")
            continue

        ing_lines = []
        for i in recipe.get("ingredients", []):
            ing_lines.append(f"- {i.get('amount', '')} {i.get('unit', '')} {i.get('name', '')}".strip())

        inst_lines = []
        for idx, step in enumerate(recipe.get("instructions", [])):
            inst_lines.append(f"{idx + 1}. {step}")

        formatted_ingredients = "\n".join(ing_lines)
        formatted_instructions = "\n".join(inst_lines)

        description = (
            f"Meal: {recipe.get('name', '')}\n\n"
            f"{recipe.get('description', '')}\n\n"
            f"Diners: {diners_count}\n"
            f"Prep Time: {recipe.get('prepTime', '15m')} | Cook Time: {recipe.get('cookTime', '20m')}\n\n"
            f"Ingredients:\n{formatted_ingredients}\n\n"
            f"Instructions:\n{formatted_instructions}"
        )

        event_body = {
            "summary": recipe.get("name", "Dinner"),
            "location": "Home Kitchen",
            "description": description,
            "start": {
                "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Denver",
            },
            "end": {
                "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Denver",
            },
        }

        try:
            cal_service.events().insert(calendarId="primary", body=event_body).execute()
            calendar_events_created += 1
        except Exception as err:
            logger.error(f"Failed to create calendar event for '{recipe.get('name')}': {err}")
            raise AppError(f"Google Calendar API error: {err}")

    # 2. Consolidated Shopping List & Morning Groceries Event
    raw_recipes = [item["recipe"] for item in selected_recipes]
    consolidated_list = consolidate_shopping_list(raw_recipes)

    dates = sorted([item["dateVal"] for item in selected_recipes])
    earliest_date_val = dates[0] if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    e_parts = [int(p) for p in earliest_date_val.split("-")]

    grocery_start_dt = datetime(e_parts[0], e_parts[1], e_parts[2], 9, 0, 0)
    grocery_end_dt = datetime(e_parts[0], e_parts[1], e_parts[2], 10, 0, 0)

    categorized_items: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in AISLE_CATEGORIES}
    for item in consolidated_list:
        cat = item.get("category", "🥫 Pantry & Canned")
        if cat not in categorized_items:
            categorized_items[cat] = []
        categorized_items[cat].append(item)

    grocery_desc_lines = [
        "Weekly Meal Plan Grocery Shopping List",
        f"Start Date: {earliest_date_val}",
        f"Diners: {diners_count}",
        f"Recipes: {', '.join([r.get('name', '') for r in raw_recipes])}",
        "",
        "===============================",
        "ITEMS BY STORE SECTION",
        "==============================="
    ]

    for cat in AISLE_CATEGORIES:
        items = categorized_items.get(cat, [])
        if items:
            grocery_desc_lines.append("")
            grocery_desc_lines.append(cat)
            for itm in items:
                amount_str = ", ".join([f"{a['amount']} {a['unit']}".strip() for a in itm.get("amounts", [])])
                item_name = itm["name"].capitalize()
                grocery_desc_lines.append(f"• {item_name}: {amount_str}")

    grocery_event_body = {
        "summary": "🛒 Groceries",
        "location": "Grocery Store",
        "description": "\n".join(grocery_desc_lines),
        "start": {
            "dateTime": grocery_start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "America/Denver",
        },
        "end": {
            "dateTime": grocery_end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "America/Denver",
        },
    }

    try:
        cal_service.events().insert(calendarId="primary", body=grocery_event_body).execute()
        groceries_event_created = True
    except Exception as err:
        logger.error(f"Failed to create Groceries calendar event: {err}")
        groceries_event_created = False

    return {
        "calendarEventsCreated": calendar_events_created,
        "groceriesEventCreated": groceries_event_created,
        "shoppingList": consolidated_list
    }
