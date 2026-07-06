import uuid


def short_id() -> str:
    return uuid.uuid4().hex[:8]
