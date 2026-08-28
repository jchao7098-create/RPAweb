"""Department naming rules shared by writes, API responses, and exports.

The database contains historical free-text values such as ``客服`` / ``客服部``
and even values where a project title was pasted after the department name.
Normalizing at the application boundary keeps those records in one visual group
without changing the production database or requiring a data migration.
"""

import re
import unicodedata


STANDARD_DEPARTMENTS = (
    '运营A组',
    '运营E组',
    '项目部',
    '客服部',
    '财务部',
    '供应链部',
    '人事行政部',
    'AI应用部',
)
OTHER_DEPARTMENT = '其他'


_DIRECT_ALIASES = {
    '客服': '客服部',
    '客服部门': '客服部',
    '客服组': '客服部',
    '人事': '人事行政部',
    '人事部': '人事行政部',
    '人事部门': '人事行政部',
    '行政': '人事行政部',
    '行政部': '人事行政部',
    '行政部门': '人事行政部',
    '人事行政': '人事行政部',
    '人事行政部门': '人事行政部',
    '供应链': '供应链部',
    '供应链部门': '供应链部',
    '财务': '财务部',
    '财务部门': '财务部',
    '项目': '项目部',
    '项目部门': '项目部',
    '项目组': '项目部',
    '运营A': '运营A组',
    'A组': '运营A组',
    '运营E': '运营E组',
    '运营E组': '运营E组',
    'E组': '运营E组',
    'AI应用': 'AI应用部',
    'AI应用部门': 'AI应用部',
    '人工智能应用部': 'AI应用部',
    '未指定部门': OTHER_DEPARTMENT,
}

_DEPARTMENT_SUFFIXES = ('部', '组', '中心', '室', '科')


def normalize_department(value, default='未指定部门'):
    """Return one canonical label for known departments.

    Unknown values are preserved because the UI intentionally supports an
    editable ``其他`` option. Department summary pages group those values under
    ``其他`` while detail views can still display the entered description.
    """
    text = unicodedata.normalize('NFKC', str(value or ''))
    text = re.sub(r'\s+', '', text.strip())
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

    alias_key = text.upper()
    if alias_key.startswith('客服'):
        return '客服部'
    return _DIRECT_ALIASES.get(alias_key, text)


def department_group(value, default=OTHER_DEPARTMENT):
    """Return one of the configured departments or the shared ``其他`` group."""
    normalized = normalize_department(value, default=default)
    return normalized if normalized in STANDARD_DEPARTMENTS else default
