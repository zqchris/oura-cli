# oura-cli

CLI tool to fetch health data from your Oura Ring via the Oura API v2.

Zero dependencies beyond Python 3.10+ standard library. Runs with [uv](https://docs.astral.sh/uv/).

## Setup

### 1. Register an Oura API Application

Go to [Oura Developer Portal](https://cloud.ouraring.com/v2/docs) → My Applications → New Application.

Fill in:
- **Display Name**: anything
- **Description**: anything
- **Contact Email**: your email
- **Website**: any URL
- **Privacy Policy / Terms of Service**: any URL (required but not checked for personal use)
- **Redirect URIs**: `http://localhost:8080/callback`
- **Scopes**: check all

Click **Create Application**. You'll get a **Client ID** and **Client Secret**.

### 2. Authorize

```bash
uv run oauth-authorize.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

This opens your browser for Oura login → authorization → captures the callback → saves tokens locally.

Two files are created (both gitignored):
- `tokens.json` — OAuth access & refresh tokens
- `config.json` — client credentials (for auto token refresh)

### 3. Use

```bash
# Today's summary (sleep + activity + readiness)
uv run oura-data.py today

# Specific date
uv run oura-data.py today --date 2026-03-15

# Date range (no limit on range)
uv run oura-data.py sleep --start 2026-03-01 --end 2026-03-16

# Individual data types
uv run oura-data.py sleep
uv run oura-data.py activity
uv run oura-data.py readiness
uv run oura-data.py heartrate
uv run oura-data.py workout
uv run oura-data.py spo2
uv run oura-data.py stress
uv run oura-data.py ring
uv run oura-data.py personal
```

## Commands

| Command | Data |
|---------|------|
| `today` / `daily` | Sleep + Activity + Readiness combined |
| `sleep` | Score, total/deep/REM/light duration, efficiency, bedtime, HR, HRV |
| `activity` | Score, steps, calories, walking distance |
| `readiness` | Score, temperature deviation |
| `heartrate` | Min/max/avg heart rate |
| `workout` | Auto-detected and manual workouts |
| `spo2` | Blood oxygen (sleep) |
| `stress` | Stress levels |
| `ring` | Ring config & battery |
| `personal` | Age, weight, etc. |

## Token Refresh

Tokens auto-refresh on expiry (HTTP 401). No manual intervention needed as long as `config.json` exists.

## Example Output

```
=== Sleep ===

📅 2026-03-16  Sleep Score: 73
  Total: 6h18m | Deep: 1h43m | REM: 1h36m | Light: 2h59m
  Efficiency: 79%
  Bedtime: 01:28 → 09:27
  Avg HR: 68.0 | Lowest: 64 | HRV: 22

=== Activity ===

📅 2026-03-16  Activity Score: 82
  Steps: 8432 | Active Cal: 312 | Total Cal: 2156
  Walking Distance: 6.2 km

=== Readiness ===

📅 2026-03-16  Readiness Score: 73
  Temp Deviation: -0.0°C
```

## Notes

- **Sleep date quirk**: The Oura API `sleep` endpoint filters by bedtime date but returns wake-up date as `day`. This tool handles the offset automatically.
- **No date range limit**: Tested up to 365 days in a single query.
- Python 3.10+ required (uses `X | Y` union syntax).
