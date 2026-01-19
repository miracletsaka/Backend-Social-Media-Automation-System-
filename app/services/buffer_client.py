import os
import requests

BUFFER_API = "https://api.bufferapp.com/1"
TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")

class BufferError(Exception):
    pass

def _headers():
    if not TOKEN:
        raise BufferError("BUFFER_ACCESS_TOKEN not set")
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def create_update(profile_id: str, text: str, scheduled_at_iso: str | None = None):
    """
    Creates a Buffer update (post).
    scheduled_at_iso: if None -> Buffer may post immediately or use defaults depending on endpoint.
    """
    if not profile_id:
        raise BufferError("Missing Buffer profile_id")

    payload = {
        "profile_ids": [profile_id],
        "text": text,
    }

    # Buffer uses "scheduled_at" in some endpoints; keep minimal for V1.
    if scheduled_at_iso:
        payload["scheduled_at"] = scheduled_at_iso

    resp = requests.post(f"{BUFFER_API}/updates/create.json", headers=_headers(), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise BufferError(f"Buffer error {resp.status_code}: {resp.text}")

    return resp.json()
