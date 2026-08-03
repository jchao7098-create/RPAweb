import math
from datetime import datetime


PROJECT_STATUS_IN_DEVELOPMENT = '在编'
PROJECT_STATUS_IN_USE = '使用'
PROJECT_STATUS_OVERHAUL = '大修'
PROJECT_STATUS_DISABLED = '停用'
PROJECT_LIFECYCLE_STATUSES = (
    PROJECT_STATUS_IN_DEVELOPMENT,
    PROJECT_STATUS_IN_USE,
    PROJECT_STATUS_OVERHAUL,
    PROJECT_STATUS_DISABLED,
)

# Historical logs used several names for the same four lifecycle states.  They
# remain valid evidence and must participate when selecting the newest log.
PROJECT_STATUS_ALIASES = {
    PROJECT_STATUS_IN_DEVELOPMENT: PROJECT_STATUS_IN_DEVELOPMENT,
    '新编': PROJECT_STATUS_IN_DEVELOPMENT,
    '开发中': PROJECT_STATUS_IN_DEVELOPMENT,
    '测试中': PROJECT_STATUS_IN_DEVELOPMENT,
    PROJECT_STATUS_IN_USE: PROJECT_STATUS_IN_USE,
    '已完成': PROJECT_STATUS_IN_USE,
    '结束': PROJECT_STATUS_IN_USE,
    PROJECT_STATUS_OVERHAUL: PROJECT_STATUS_OVERHAUL,
    PROJECT_STATUS_DISABLED: PROJECT_STATUS_DISABLED,
    '已取消': PROJECT_STATUS_DISABLED,
}


def normalize_project_progress(value):
    """Return a finite project progress value in the supported 0-100 range."""
    try:
        progress = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('进度必须是 0 到 100 之间的数字') from exc

    if not math.isfinite(progress) or progress < 0 or progress > 100:
        raise ValueError('进度必须是 0 到 100 之间的数字')
    return progress


def project_status_for_progress(progress):
    """Legacy/asset automatic mapping; RPA display status does not use this."""
    value = normalize_project_progress(progress)
    if value == 100:
        return PROJECT_STATUS_IN_USE
    return PROJECT_STATUS_IN_DEVELOPMENT


def project_status_for_update(progress, requested_status=None):
    """Apply an optional override for assets, otherwise derive from progress."""
    if requested_status in (None, '', 'auto'):
        return project_status_for_progress(progress)
    if requested_status in PROJECT_LIFECYCLE_STATUSES:
        return requested_status
    raise ValueError('项目状态只能选择随进度自动、在编、使用、大修或停用')


def normalize_project_status(value, default=None):
    """Map current and historical status labels to the four lifecycle states."""
    return PROJECT_STATUS_ALIASES.get(value, default)


def _project_log_sort_key(log):
    return (
        getattr(log, 'log_time', None) or datetime.min,
        getattr(log, 'id', None) or -1,
    )


def project_logs_newest_first(logs):
    """Return logs in the same newest-first order used for status selection."""
    return sorted(logs, key=_project_log_sort_key, reverse=True)


def latest_lifecycle_status_from_logs(logs):
    """Return the normalized status from the newest meaningful project log.

    Newest means ``log_time DESC, id DESC``.  The id is only a deterministic
    tie-breaker for logs written at the same time.
    """
    normalized_logs = [
        (log, normalize_project_status(getattr(log, 'status', None)))
        for log in logs
    ]
    normalized_logs = [
        (log, status) for log, status in normalized_logs if status is not None
    ]
    if not normalized_logs:
        return None

    _, status = max(normalized_logs, key=lambda item: _project_log_sort_key(item[0]))
    return status


def display_status_for_project(project):
    """Use the newest log status; never infer RPA state from its progress."""
    latest = latest_lifecycle_status_from_logs(project.logs)
    if latest:
        return latest
    return normalize_project_status(
        project.status,
        default=PROJECT_STATUS_IN_DEVELOPMENT,
    )


def project_status_for_log_update(current_status, requested_status=None):
    """Resolve an RPA status update independently from the progress percentage.

    ``auto`` remains accepted for older clients, but now means "keep the newest
    logged status" instead of calculating a state from progress.
    """
    if requested_status in (None, '', 'auto'):
        return normalize_project_status(
            current_status,
            default=PROJECT_STATUS_IN_DEVELOPMENT,
        )
    normalized = normalize_project_status(requested_status)
    if normalized in PROJECT_LIFECYCLE_STATUSES:
        return normalized
    raise ValueError('项目状态只能选择在编、使用、大修或停用')
