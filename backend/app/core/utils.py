from datetime import datetime, timedelta, timezone

import ulid

from app.core.config import settings


def get_ulid() -> str:
    return str(ulid.ULID())


def default_share_expiry(now: datetime | None = None) -> datetime:
    """
    When a share expires if the sharer did not choose a date.

    One helper for both share kinds. A per-recipient grant used to default to a
    week while a public link had no expiry at all, so the same "Поделиться"
    button meant two different things depending on which tab you were on.
    """
    now = now or datetime.now(timezone.utc)
    return now + timedelta(days=settings.share_expiry_days)
