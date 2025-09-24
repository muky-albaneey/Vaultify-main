# from django.utils import timezone
# import pytz

# LAGOS = pytz.timezone("Africa/Lagos")

# def to_local_iso(dt):
#     if not dt:
#         return None
#     return dt.astimezone(LAGOS).replace(microsecond=0).isoformat()

# def assume_lagos_then_to_utc(dt):
#     """
#     If the client sends a naive datetime (no offset), treat it as Africa/Lagos,
#     then convert to UTC for storage. If aware, leave it, but store as UTC.
#     """
#     if not dt:
#         return None
#     if timezone.is_naive(dt):
#         dt = LAGOS.localize(dt)
#     # normalize to UTC for DB
#     return dt.astimezone(timezone.utc)
# accounts/timefmt.py
from datetime import timezone as dt_timezone
from django.utils import timezone
import pytz

LAGOS = pytz.timezone("Africa/Lagos")

def to_local_iso(dt):
    if not dt:
        return None
    # ensure aware before converting (handles any naive DB values defensively)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    return dt.astimezone(LAGOS).replace(microsecond=0).isoformat()

def assume_lagos_then_to_utc(dt):
    """
    If the client sends a naive datetime (no offset), treat it as Africa/Lagos,
    then convert to UTC for storage. If aware, leave it, but store as UTC.
    """
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = LAGOS.localize(dt)  # interpret as Lagos local time
    # normalize to UTC for DB
    return dt.astimezone(dt_timezone.utc)  # <-- was timezone.utc (removed in Django 5)
