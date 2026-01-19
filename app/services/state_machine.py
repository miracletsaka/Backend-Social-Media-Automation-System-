from app.utils.constants import STATES

ALLOWED_TRANSITIONS = {
    "TOPIC_INGESTED": ["GENERATING", "PENDING_APPROVAL"],
    "GENERATING": ["DRAFT_READY", "FAILED"],
    "DRAFT_READY": ["PENDING_APPROVAL", "FAILED"],
    "PENDING_APPROVAL": ["APPROVED", "REJECTED", "FAILED"],
    "APPROVED": ["SCHEDULED", "FAILED"],
    "REJECTED": ["GENERATING", "FAILED"],
    "SCHEDULED": ["QUEUED", "FAILED", "PUBLISHED"],   # ✅ changed
    "QUEUED": ["PUBLISHED", "SCHEDULED", "FAILED"],   # ✅ new
    "PUBLISHED": [],
    "FAILED": ["SCHEDULED"],
}

def ensure_transition(current: str, target: str) -> None:
    if current not in STATES:
        raise ValueError(f"Unknown state: {current}")
    if target not in STATES:
        raise ValueError(f"Unknown target state: {target}")

    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(f"Invalid transition: {current} -> {target}")
