import json
import os
from urllib import request, error


def _build_payload(email, first_name, result_payload, metadata):
    result_key = result_payload.get("result_key")
    tags = ["Quiz - Completed", str(result_key or "").strip().upper()]
    tags = [tag for tag in tags if tag]

    payload = {
        "email": email,
        "firstname": first_name or "",
        "tags": list(dict.fromkeys(tags)),
        "upsert": True,
        "append_tags": True,
        "source": "gracewise_homeschool_style_quiz",
        "metadata": metadata or {}
    }
    return payload


def push_quiz_lead_to_systeme(email, first_name, result_payload, metadata=None):
    """
    Push quiz lead to Systeme (typically via Zapier Catch Hook URL).
    Returns (status, response_text)
    status in: synced, skipped, failed
    """
    webhook_url = (os.environ.get("SYSTEME_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        return "skipped", "SYSTEME_WEBHOOK_URL is not configured"

    payload = _build_payload(email, first_name, result_payload, metadata)
    body = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    auth_header_name = (os.environ.get("SYSTEME_WEBHOOK_AUTH_HEADER") or "").strip()
    auth_header_value = (os.environ.get("SYSTEME_WEBHOOK_AUTH_VALUE") or "").strip()
    if auth_header_name and auth_header_value:
        headers[auth_header_name] = auth_header_value

    req = request.Request(webhook_url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=12) as resp:
            response_text = resp.read().decode("utf-8", errors="ignore")
            return "synced", response_text[:5000]
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
        return "failed", f"HTTP {exc.code}: {response_text[:2000]}"
    except Exception as exc:
        return "failed", str(exc)
