"""Department naming rules shared by writes, API responses, and exports.

The database contains historical free-text values such as ``客服`` / ``客服部``
and even values where a project title was pasted after the department name.
Normalizing at the application boundary keeps those records in one visual group
without changing the production database or requiring a data migration.
"""

import re


_DIRECT_ALIASES = {
    '客服': '客服部',
    '客服部门': '客服部',
    '客服组': '客服部',
    '人事': '人事部',
    '人事部门': '人事部',
    '供应链': '供应链部',
    '供应链部门': '供应链部',
    '市场': '市场部',
    '市场部门': '市场部',
    '财务': '财务部',
    '财务部门': '财务部',
    '行政': '行政部',
    '行政部门': '行政部',
    '项目': '项目部',
    '项目部门': '项目部',
    '运营A': '运营A组',
}

_DEPARTMENT_SUFFIXES = ('部', '组', '中心', '室', '科')


def normalize_department(value, default='未指定部门'):
    """Return a stable department label while preserving unknown valid names."""
    text = re.sub(r'\s+', '', str(value or '').strip())
    if not text:
        return default

    # Treat a trailing site/team note as metadata, not a new department:
    # 运营A组（杏花楼） -> 运营A组.
    parenthetical = re.match(r'^(.+?)[（(][^）)]*[）)]$', text)
    if parenthetical and parenthetical.group(1).endswith(_DEPARTMENT_SUFFIXES):
        text = parenthetical.group(1)

    # Historical bad input sometimes contains the whole project title:
    # 客服部-售后-... -> 客服部.
    first_segment = re.split(r'[-—–_]', text, maxsplit=1)[0]
    if (
        first_segment in _DIRECT_ALIASES
        or first_segment.endswith(_DEPARTMENT_SUFFIXES)
    ):
        text = first_segment

    if text.startswith('客服'):
        return '客服部'
    return _DIRECT_ALIASES.get(text, text)
