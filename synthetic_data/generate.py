"""
Synthetic Data Generator
=========================
Generates realistic mock health data for the 3 patient profiles.
This data is used by mock_apis.py to simulate Google Fit / FHIR responses.

Run:
    cd synthetic_data
    python generate.py
"""

import json
import random
import os
from datetime import datetime, timedelta


def generate_daily_data(days: int, hr_range: tuple, steps_range: tuple, sleep_range: tuple) -> dict:
    """Generate daily health data for a given number of days."""
    data = {
        "daily_hr": [],
        "daily_steps": [],
        "daily_sleep": [],
    }
    for _ in range(days):
        data["daily_hr"].append(random.randint(*hr_range))
        data["daily_steps"].append(random.randint(*steps_range))
        data["daily_sleep"].append(round(random.uniform(*sleep_range), 1))
    return data


def generate_recovery_trend(days: int) -> dict:
    """Generate improving trend data (HR going down, steps going up)."""
    data = {"daily_hr": [], "daily_steps": [], "daily_sleep": []}
    for i in range(days):
        progress = i / max(days - 1, 1)  # 0.0 → 1.0
        hr = int(95 - (progress * 22) + random.randint(-3, 3))
        steps = int(4500 + (progress * 4000) + random.randint(-300, 300))
        sleep = round(5.2 + (progress * 2.5) + random.uniform(-0.3, 0.3), 1)
        data["daily_hr"].append(max(60, hr))
        data["daily_steps"].append(max(1000, steps))
        data["daily_sleep"].append(min(9.0, max(4.0, sleep)))
    return data


PROFILES = {
    "healthy": {
        "description": "Normal healthy adult — stable vitals",
        "hr_range": (62, 78),
        "steps_range": (8000, 11000),
        "sleep_range": (7.0, 8.5),
        "records": {
            "summary": "No chronic conditions. Last annual checkup: 3 months ago — all clear.",
            "medications": [],
            "allergies": ["Penicillin"],
        },
    },
    "at_risk": {
        "description": "Hypertension stage 1 — elevated HR, poor sleep",
        "hr_range": (95, 115),
        "steps_range": (2500, 4000),
        "sleep_range": (4.0, 5.8),
        "records": {
            "summary": "Hypertension stage 1 diagnosed 6 months ago. On daily monitoring.",
            "medications": ["Lisinopril 10mg"],
            "allergies": [],
        },
    },
    "recovery": {
        "description": "Post-surgery recovery — improving trend over 7 days",
        "hr_range": (72, 92),
        "steps_range": (4500, 8500),
        "sleep_range": (5.2, 7.8),
        "records": {
            "summary": "Post-surgery recovery (appendectomy, 3 weeks ago). Vitals trending positive.",
            "medications": ["Ibuprofen 400mg PRN"],
            "allergies": ["Sulfa drugs"],
        },
    },
}


def generate_all():
    """Generate synthetic data for all profiles and save to JSON."""
    output = {}

    for name, profile in PROFILES.items():
        if name == "recovery":
            daily = generate_recovery_trend(7)
        else:
            daily = generate_daily_data(7, profile["hr_range"], profile["steps_range"], profile["sleep_range"])

        avg_hr = round(sum(daily["daily_hr"]) / len(daily["daily_hr"]), 1)
        avg_steps = round(sum(daily["daily_steps"]) / len(daily["daily_steps"]))
        avg_sleep = round(sum(daily["daily_sleep"]) / len(daily["daily_sleep"]), 1)

        output[name] = {
            "description": profile["description"],
            "current_hr_bpm": random.randint(*profile["hr_range"]),
            "weekly_vitals": {
                "avg_hr_bpm": avg_hr,
                "avg_steps": avg_steps,
                "avg_sleep_hours": avg_sleep,
                **daily,
            },
            "records": profile["records"],
        }

    out_path = os.path.join(os.path.dirname(__file__), "profiles.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Generated synthetic data for {len(output)} profiles → {out_path}")
    for name, data in output.items():
        print(f"  {name}: HR={data['current_hr_bpm']} bpm, "
              f"avg steps={data['weekly_vitals']['avg_steps']}, "
              f"avg sleep={data['weekly_vitals']['avg_sleep_hours']}h")


if __name__ == "__main__":
    generate_all()
