"""
Unit tests for calendar_service: time parsing and event scheduling logic.
"""

from datetime import datetime
from unittest.mock import MagicMock
import pytest

from services.calendar_service import parse_time_str, schedule_approved_meals


def test_parse_time_str():
    # Standard 12-hour formats
    assert parse_time_str("10:00am") == (10, 0)
    assert parse_time_str("10:00 AM") == (10, 0)
    assert parse_time_str("10am") == (10, 0)
    assert parse_time_str("5:30pm") == (17, 30)
    assert parse_time_str("12:00pm") == (12, 0)
    assert parse_time_str("12:00am") == (0, 0)
    assert parse_time_str("11:45pm") == (23, 45)

    # 24-hour formats
    assert parse_time_str("14:30") == (14, 30)
    assert parse_time_str("09:15") == (9, 15)

    # Defaults and fallbacks
    assert parse_time_str("", default=(10, 0)) == (10, 0)
    assert parse_time_str(None, default=(10, 0)) == (10, 0)
    assert parse_time_str("invalid", default=(10, 0)) == (10, 0)
    assert parse_time_str("") == (17, 30)


def test_schedule_approved_meals_grocery_next_instance_today(sample_recipes):
    """
    When current time is before the default grocery time (e.g., 08:30 AM vs 10:00 AM),
    the grocery event should be scheduled for today at 10:00 AM.
    """
    mock_creds = MagicMock()
    mock_events = MagicMock()
    created_events = []

    def mock_insert(calendarId, body):
        mock_req = MagicMock()
        mock_req.execute.return_value = {"id": f"event_{len(created_events)}"}
        created_events.append(body)
        return mock_req

    mock_events.insert.side_effect = mock_insert
    mock_cal_service = MagicMock()
    mock_cal_service.events.return_value = mock_events
    mock_cal_service.calendars().get().execute.return_value = {"timeZone": "America/Denver"}

    # Mock build
    from unittest.mock import patch
    with patch("services.calendar_service.build", return_value=mock_cal_service):
        approved = [
            {"name": sample_recipes[0]["name"], "date": "2026-10-15"}
        ]
        preferences = {
            "dinersCount": 4,
            "defaultMealTime": "6:00pm",
            "defaultGroceryTime": "10:00am"
        }
        ref_time = datetime(2026, 10, 10, 8, 30, 0)  # 8:30 AM

        result = schedule_approved_meals(
            approved_meals_with_dates=approved,
            all_recipes=sample_recipes,
            preferences=preferences,
            credentials=mock_creds,
            current_time=ref_time
        )

    assert result["calendarEventsCreated"] == 1
    assert result["groceriesEventCreated"] is True

    # Dinner event + grocery event = 2 events
    assert len(created_events) == 2
    dinner_event = created_events[0]
    grocery_event = created_events[1]

    assert dinner_event["summary"] == sample_recipes[0]["name"]
    assert dinner_event["start"]["dateTime"] == "2026-10-15T18:00:00"

    assert grocery_event["summary"] == "🛒 Groceries"
    # Scheduled for same day 10:00 AM because 8:30 AM < 10:00 AM
    assert grocery_event["start"]["dateTime"] == "2026-10-10T10:00:00"
    assert grocery_event["end"]["dateTime"] == "2026-10-10T11:00:00"


def test_schedule_approved_meals_grocery_next_instance_tomorrow(sample_recipes):
    """
    When current time is after the default grocery time (e.g., 1:15 PM vs 10:00 AM),
    the grocery event should be scheduled for the next day at 10:00 AM.
    """
    mock_creds = MagicMock()
    mock_events = MagicMock()
    created_events = []

    def mock_insert(calendarId, body):
        mock_req = MagicMock()
        mock_req.execute.return_value = {"id": f"event_{len(created_events)}"}
        created_events.append(body)
        return mock_req

    mock_events.insert.side_effect = mock_insert
    mock_cal_service = MagicMock()
    mock_cal_service.events.return_value = mock_events
    mock_cal_service.calendars().get().execute.return_value = {"timeZone": "America/Denver"}

    from unittest.mock import patch
    with patch("services.calendar_service.build", return_value=mock_cal_service):
        approved = [
            {"name": sample_recipes[0]["name"], "date": "2026-10-15"}
        ]
        preferences = {
            "dinersCount": 4,
            "defaultMealTime": "5:30pm",
            "defaultGroceryTime": "10:00am"
        }
        ref_time = datetime(2026, 10, 10, 13, 15, 0)  # 1:15 PM

        result = schedule_approved_meals(
            approved_meals_with_dates=approved,
            all_recipes=sample_recipes,
            preferences=preferences,
            credentials=mock_creds,
            current_time=ref_time
        )

    assert result["calendarEventsCreated"] == 1
    assert result["groceriesEventCreated"] is True

    grocery_event = created_events[1]
    assert grocery_event["summary"] == "🛒 Groceries"
    # Scheduled for next day (Oct 11) at 10:00 AM because 1:15 PM > 10:00 AM
    assert grocery_event["start"]["dateTime"] == "2026-10-11T10:00:00"
    assert grocery_event["end"]["dateTime"] == "2026-10-11T11:00:00"
