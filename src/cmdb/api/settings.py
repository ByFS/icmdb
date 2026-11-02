"""System settings: DB key-value store, environment variables as defaults"""

import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from cmdb.api.auth import current_username
from cmdb.config import settings as app_settings
from cmdb.database import get_session
from cmdb.models import SystemSetting
from cmdb.services.audit import record_audit

router = APIRouter(tags=["settings"])

OFFLINE_THRESHOLD_KEY = "offline_threshold_hours"
API_KEY_ENABLED_KEY = "api_key_enabled"


def get_offline_threshold_hours(session: Session) -> int:
    """Suspected offline threshold (hours): DB setting takes priority, falls back to environment variables (days x 24)"""
    row = session.exec(
        select(SystemSetting).where(SystemSetting.key == OFFLINE_THRESHOLD_KEY)
    ).first()
    if row and row.value and row.value.strip().isdigit():
        return int(row.value)
    return app_settings.offline_threshold_days * 24


# seconds; without invalidation a toggle takes effect within this window
_API_KEY_CACHE_TTL = 5.0
_api_key_cache: tuple[bool, float] | None = None


def get_api_key_enabled_cached() -> bool:
    """Cached toggle read for the middleware

    The middleware runs per request, a DB round trip per request would hold
    extra pool connections under concurrency
    """
    global _api_key_cache

    # Lazy import: resolved at call time, picks up the test monkeypatch
    from cmdb.database import get_engine_cached

    now = time.monotonic()
    if _api_key_cache is not None:
        value, cached_at = _api_key_cache
        if now - cached_at < _API_KEY_CACHE_TTL:
            return value
    with Session(get_engine_cached()) as session:
        value = get_api_key_enabled(session)
    _api_key_cache = (value, now)
    return value


def invalidate_api_key_cache() -> None:
    """Drop the cached toggle so a settings change takes effect immediately"""
    global _api_key_cache
    _api_key_cache = None


def get_api_key_enabled(session: Session) -> bool:
    """API key feature toggle (DB setting api_key_enabled, default off)"""
    row = session.exec(
        select(SystemSetting).where(SystemSetting.key == API_KEY_ENABLED_KEY)
    ).first()
    return bool(row and row.value == "1")


class SystemSettingsOut(BaseModel):
    offline_threshold_hours: int
    api_key_enabled: bool


class SystemSettingsIn(BaseModel):
    offline_threshold_hours: int = Field(ge=1, le=24 * 365)
    api_key_enabled: bool | None = None


@router.get("/settings/system")
def read_system_settings(
    session: Session = Depends(get_session),
) -> SystemSettingsOut:
    return SystemSettingsOut(
        offline_threshold_hours=get_offline_threshold_hours(session),
        api_key_enabled=get_api_key_enabled(session),
    )


@router.put("/settings/system")
def update_system_settings(
    body: SystemSettingsIn,
    request: Request,
    session: Session = Depends(get_session),
) -> SystemSettingsOut:
    old_value = get_offline_threshold_hours(session)
    row = session.exec(
        select(SystemSetting).where(SystemSetting.key == OFFLINE_THRESHOLD_KEY)
    ).first()
    if row:
        row.value = str(body.offline_threshold_hours)
    else:
        row = SystemSetting(key=OFFLINE_THRESHOLD_KEY, value=str(body.offline_threshold_hours))
    session.add(row)

    # API key feature toggle (None = keep, stored as "1"/"0")
    old_enabled = get_api_key_enabled(session)
    toggle_changed = False
    if body.api_key_enabled is not None and body.api_key_enabled != old_enabled:
        enabled_row = session.exec(
            select(SystemSetting).where(SystemSetting.key == API_KEY_ENABLED_KEY)
        ).first()
        value = "1" if body.api_key_enabled else "0"
        if enabled_row:
            enabled_row.value = value
        else:
            enabled_row = SystemSetting(key=API_KEY_ENABLED_KEY, value=value)
        session.add(enabled_row)
        record_audit(
            session, current_username(request), "修改系统设置",
            f"API 密钥 {'开启' if body.api_key_enabled else '关闭'}",
        )
        toggle_changed = True

    record_audit(
        session, current_username(request), "修改系统设置",
        f"疑似下线阈值 {old_value} -> {body.offline_threshold_hours} 小时",
    )
    session.commit()
    # Drop the cached toggle only after the new value is visible; invalidating
    # before the commit lets a concurrent request re-cache the stale value for
    # the whole TTL window
    if toggle_changed:
        invalidate_api_key_cache()
    return SystemSettingsOut(
        offline_threshold_hours=body.offline_threshold_hours,
        api_key_enabled=get_api_key_enabled(session),
    )
