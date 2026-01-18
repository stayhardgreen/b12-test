#!/usr/bin/env python3
import os
import json
import hmac
import hashlib
import datetime
import urllib.request
import urllib.error

B12_ENDPOINT = "https://b12.io/apply/submission"

def iso8601_utc_now_ms() -> str:
    # e.g. 2026-01-06T16:59:37.571Z
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

def require_env(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v

def main() -> None:
    # Required fields from B12 prompt
    name = require_env("B12_NAME")
    email = require_env("B12_EMAIL")
    resume_link = require_env("B12_RESUME_LINK")

    # Derive repo + action run links (GitHub Actions)
    server_url = require_env("GITHUB_SERVER_URL")          # e.g. https://github.com
    repo = require_env("GITHUB_REPOSITORY")                # e.g. owner/repo
    run_id = require_env("GITHUB_RUN_ID")                  # e.g. 20561457327

    repository_link = f"{server_url}/{repo}"
    action_run_link = f"{server_url}/{repo}/actions/runs/{run_id}"

    payload = {
        "timestamp": iso8601_utc_now_ms(),
        "name": name,
        "email": email,
        "resume_link": resume_link,
        "repository_link": repository_link,
        "action_run_link": action_run_link,
    }

    # Canonical JSON: keys sorted, compact separators, UTF-8
    body_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    body_bytes = body_str.encode("utf-8")

    # HMAC-SHA256 signature over raw UTF-8 JSON body
    signing_secret = os.getenv("B12_SIGNING_SECRET", "hello-there-from-b12").encode("utf-8")
    digest = hmac.new(signing_secret, body_bytes, hashlib.sha256).hexdigest()
    signature_header = f"sha256={digest}"

    req = urllib.request.Request(
        B12_ENDPOINT,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Signature-256": signature_header,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} error from B12: {err_body}") from e

    # Expect: {"success": true, "receipt": "your-submission-receipt"}
    try:
        data = json.loads(resp_body)
    except json.JSONDecodeError:
        raise SystemExit(f"Non-JSON response from B12: {resp_body}")

    if not data.get("success") or "receipt" not in data:
        raise SystemExit(f"Unexpected response from B12: {data}")

    # Print receipt for CI logs
    print(data["receipt"])

if __name__ == "__main__":
    main()
