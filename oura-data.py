#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Fetch Oura ring data via API v2.

Usage:
    uv run oura-data.py <command> [--date YYYY-MM-DD] [--start YYYY-MM-DD] [--end YYYY-MM-DD]

Commands:
    today       - Sleep, activity, readiness for today
    sleep       - Sleep data (score + durations)
    activity    - Activity/steps data
    readiness   - Readiness score
    heartrate   - Heart rate summary
    daily       - Same as today
    workout     - Workouts
    spo2        - Blood oxygen
    stress      - Stress data
    ring        - Ring info & battery
    personal    - Personal info (age, weight, etc.)
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API_BASE = "https://api.ouraring.com/v2/usercollection"
TOKEN_FILE = Path(__file__).parent / "tokens.json"
TOKEN_URL = "https://api.ouraring.com/oauth/token"

CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("Error: config.json not found. Create it with client_id and client_secret.", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())


def load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        print("Error: No tokens found. Run oauth-authorize.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(TOKEN_FILE.read_text())


def save_tokens(tokens: dict):
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def refresh_access_token(tokens: dict) -> dict:
    config = load_config()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        new_tokens = json.loads(resp.read())
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    save_tokens(new_tokens)
    return new_tokens


# Global state for auto-refresh
_tokens: dict = {}


def api_get(path: str, params: dict | None = None) -> dict:
    global _tokens
    url = f"{API_BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    for attempt in range(2):
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {_tokens['access_token']}")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                print("Token expired, auto-refreshing...", file=sys.stderr)
                _tokens = refresh_access_token(_tokens)
                continue
            body = e.read().decode() if e.readable() else ""
            print(f"API error {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
    return {}


def fmt_duration(secs):
    if secs is None:
        return "?"
    h, m = divmod(int(secs) // 60, 60)
    return f"{int(h)}h{int(m)}m"


def format_sleep(daily_data: dict, detail_data: dict | None = None):
    # Both endpoints use the same "day" value (wake-up date)
    detail_by_day: dict[str, dict] = {}
    if detail_data:
        for item in detail_data.get("data", []):
            if item.get("type") == "long_sleep":
                detail_by_day[item.get("day", "")] = item

    for item in daily_data.get("data", []):
        day = item.get("day", "?")
        score = item.get("score", "?")
        contributors = item.get("contributors", {})

        detail = detail_by_day.get(day, {})

        total = detail.get("total_sleep_duration")
        deep = detail.get("deep_sleep_duration")
        rem = detail.get("rem_sleep_duration")
        light = detail.get("light_sleep_duration")
        efficiency = detail.get("efficiency")
        avg_hr = detail.get("average_heart_rate")
        avg_hrv = detail.get("average_hrv")
        lowest_hr = detail.get("lowest_heart_rate")
        bedtime_start = detail.get("bedtime_start", "")
        bedtime_end = detail.get("bedtime_end", "")

        print(f"\n📅 {day}  Sleep Score: {score}")
        print(f"  Total: {fmt_duration(total)} | Deep: {fmt_duration(deep)} | REM: {fmt_duration(rem)} | Light: {fmt_duration(light)}")
        if efficiency is not None:
            print(f"  Efficiency: {efficiency}%")
        if bedtime_start and bedtime_end:
            # Extract time portion
            t_start = bedtime_start[11:16] if len(bedtime_start) > 16 else bedtime_start
            t_end = bedtime_end[11:16] if len(bedtime_end) > 16 else bedtime_end
            print(f"  Bedtime: {t_start} → {t_end}")
        if avg_hr is not None or avg_hrv is not None:
            parts = []
            if avg_hr is not None:
                parts.append(f"Avg HR: {avg_hr}")
            if lowest_hr is not None:
                parts.append(f"Lowest: {lowest_hr}")
            if avg_hrv is not None:
                parts.append(f"HRV: {avg_hrv}")
            print(f"  {' | '.join(parts)}")
        if contributors:
            parts = [f"{k}: {v}" for k, v in contributors.items() if v is not None]
            if parts:
                print(f"  Contributors: {', '.join(parts)}")


def format_activity(data: dict):
    for item in data.get("data", []):
        day = item.get("day", "?")
        score = item.get("score", "?")
        steps = item.get("steps", "?")
        cal = item.get("active_calories", "?")
        total_cal = item.get("total_calories", "?")
        distance = item.get("equivalent_walking_distance")
        print(f"\n📅 {day}  Activity Score: {score}")
        print(f"  Steps: {steps} | Active Cal: {cal} | Total Cal: {total_cal}")
        if distance is not None:
            print(f"  Walking Distance: {distance/1000:.1f} km")


def format_readiness(data: dict):
    for item in data.get("data", []):
        day = item.get("day", "?")
        score = item.get("score", "?")
        temp_dev = item.get("temperature_deviation")
        contributors = item.get("contributors", {})
        print(f"\n📅 {day}  Readiness Score: {score}")
        if temp_dev is not None:
            print(f"  Temp Deviation: {temp_dev:+.1f}°C")
        if contributors:
            parts = [f"{k}: {v}" for k, v in contributors.items() if v is not None]
            if parts:
                print(f"  Contributors: {', '.join(parts)}")


def format_heartrate(data: dict):
    items = data.get("data", [])
    if not items:
        print("No heart rate data.")
        return
    bpms = [i["bpm"] for i in items if "bpm" in i]
    if bpms:
        print(f"Heart Rate — Min: {min(bpms)} | Max: {max(bpms)} | Avg: {sum(bpms)//len(bpms)} | Samples: {len(bpms)}")


def format_generic(data: dict, label: str):
    items = data.get("data", [])
    if not items:
        print(f"No {label} data.")
        return
    print(json.dumps(items, indent=2, ensure_ascii=False))


def main():
    global _tokens

    parser = argparse.ArgumentParser(description="Fetch Oura ring data")
    parser.add_argument("command", choices=[
        "today", "sleep", "activity", "readiness", "heartrate",
        "daily", "workout", "spo2", "stress", "ring", "personal",
    ])
    parser.add_argument("--date", help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    _tokens = load_tokens()

    # Date range
    today_str = date.today().isoformat()
    if args.date:
        start_date = end_date = args.date
    elif args.start:
        start_date = args.start
        end_date = args.end or today_str
    else:
        start_date = end_date = today_str

    params = {"start_date": start_date, "end_date": end_date}
    # sleep endpoint filters by bedtime date, but day field = wake-up date
    # So to get sleep with day=X, need start_date=X-1 (bedtime was previous night)
    start_minus_one = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    sleep_params = {"start_date": start_minus_one, "end_date": end_date}

    cmd = args.command

    if cmd == "personal":
        print(json.dumps(api_get("personal_info"), indent=2, ensure_ascii=False))
        return

    if cmd == "ring":
        data = api_get("ring_configuration")
        print(json.dumps(data.get("data", data), indent=2, ensure_ascii=False))
        return

    if cmd in ("today", "daily"):
        print("=== Sleep ===")
        format_sleep(api_get("daily_sleep", params), api_get("sleep", sleep_params))
        print("\n=== Activity ===")
        format_activity(api_get("daily_activity", params))
        print("\n=== Readiness ===")
        format_readiness(api_get("daily_readiness", params))
        return

    if cmd == "sleep":
        format_sleep(api_get("daily_sleep", params), api_get("sleep", sleep_params))
        return

    endpoint_map = {
        "activity": ("daily_activity", format_activity),
        "readiness": ("daily_readiness", format_readiness),
        "heartrate": ("heartrate", format_heartrate),
        "workout": ("workout", lambda d: format_generic(d, "workout")),
        "spo2": ("daily_spo2", lambda d: format_generic(d, "SpO2")),
        "stress": ("daily_stress", lambda d: format_generic(d, "stress")),
    }

    endpoint, formatter = endpoint_map[cmd]
    formatter(api_get(endpoint, params))


if __name__ == "__main__":
    main()
