from app.departments import department_group, normalize_department


def test_normalizes_common_department_aliases():
    assert normalize_department('客服') == '客服部'
    assert normalize_department(' 客服部门 ') == '客服部'
    assert normalize_department('供应链') == '供应链部'
    assert normalize_department('人事') == '人事行政部'
    assert normalize_department('人事部') == '人事行政部'
    assert normalize_department('行政部') == '人事行政部'
    assert normalize_department('运营A') == '运营A组'
    assert normalize_department('运营e组') == '运营E组'
    assert normalize_department('E组') == '运营E组'


def test_merges_project_text_and_trailing_team_notes():
    assert normalize_department('客服部-售后-消息触达') == '客服部'
    assert normalize_department('运营A组（杏花楼）') == '运营A组'


def test_preserves_unknown_department_names():
    assert normalize_department('电商A组') == '电商A组'
    assert normalize_department(None) == '未指定部门'
    assert normalize_department('', default='') == ''


def test_groups_custom_departments_under_other():
    assert department_group('客服部门') == '客服部'
    assert department_group('市场部') == '其他'
    assert department_group('自定义新部门') == '其他'
