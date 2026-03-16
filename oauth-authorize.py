#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
One-time OAuth2 authorization for Oura API.
Opens browser → user authorizes → captures callback → exchanges for tokens → saves to .env file.

Usage:
    uv run oauth-authorize.py --client-id ID --client-secret SECRET
"""

import argparse
import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "email personal daily heartrate workout tag session spo2 ring_configuration stress heart_health"

TOKEN_FILE = Path(__file__).parent / "tokens.json"
CONFIG_FILE = Path(__file__).parent / "config.json"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description="Oura OAuth2 Authorization")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    auth_code = None
    server_error = None

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code, server_error
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>OK! Token received. You can close this tab.</h1>")
            else:
                server_error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {server_error}</h1>".encode())

        def log_message(self, format, *a):
            pass  # suppress logs

    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "oura_openclaw",
    })
    auth_url = f"{AUTHORIZE_URL}?{auth_params}"

    # Start local server
    server = http.server.HTTPServer(("127.0.0.1", args.port), CallbackHandler)
    server.timeout = 120

    print(f"Opening browser for Oura authorization...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    print(f"Waiting for callback on port {args.port} (timeout 120s)...")

    # Wait for one request
    while auth_code is None and server_error is None:
        server.handle_request()

    server.server_close()

    if server_error:
        print(f"Authorization failed: {server_error}", file=sys.stderr)
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")

    tokens = exchange_code(args.client_id, args.client_secret, auth_code)

    # Save tokens
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))

    # Save client credentials to config.json (for token refresh)
    CONFIG_FILE.write_text(json.dumps({
        "client_id": args.client_id,
        "client_secret": args.client_secret,
    }, indent=2))

    print(f"\nTokens saved to: {TOKEN_FILE}")
    print(f"Config saved to: {CONFIG_FILE}")
    print(f"Access token expires in: {tokens.get('expires_in', '?')} seconds")
    if tokens.get("refresh_token"):
        print("Refresh token: saved (for auto-renewal)")


if __name__ == "__main__":
    main()
