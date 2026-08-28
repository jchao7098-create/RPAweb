export const STANDARD_DEPARTMENTS = Object.freeze([
  '运营A组',
  '运营E组',
  '项目部',
  '客服部',
  '财务部',
  '供应链部',
  '人事行政部',
  'AI应用部',
])

export const OTHER_DEPARTMENT = '其他'
export const DEPARTMENT_OPTIONS = Object.freeze([
  ...STANDARD_DEPARTMENTS.map((value) => ({ label: value, value })),
  { label: '其他（可编辑）', value: OTHER_DEPARTMENT },
])

const DIRECT_ALIASES = {
  客服: '客服部',
  客服部门: '客服部',
  客服组: '客服部',
  人事: '人事行政部',
  人事部: '人事行政部',
  人事部门: '人事行政部',
  行政: '人事行政部',
  行政部: '人事行政部',
  行政部门: '人事行政部',
  人事行政: '人事行政部',
  人事行政部门: '人事行政部',
  供应链: '供应链部',
  供应链部门: '供应链部',
  财务: '财务部',
  财务部门: '财务部',
  项目: '项目部',
  项目部门: '项目部',
  项目组: '项目部',
  运营A: '运营A组',
  A组: '运营A组',
  运营E: '运营E组',
  运营E组: '运营E组',
  E组: '运营E组',
  AI应用: 'AI应用部',
  AI应用部门: 'AI应用部',
  人工智能应用部: 'AI应用部',
  未指定部门: OTHER_DEPARTMENT,
}

const DEPARTMENT_SUFFIXES = ['部', '组', '中心', '室', '科']
const hasDepartmentSuffix = (value) =>
  DEPARTMENT_SUFFIXES.some((suffix) => value.endsWith(suffix))

export const normalizeDepartment = (value, fallback = '未指定部门') => {
  let text = String(value ?? '').normalize('NFKC').trim().replace(/\s+/g, '')
  if (!text) return fallback

  const parenthetical = text.match(/^(.+?)[（(][^）)]*[）)]$/)
  if (parenthetical && hasDepartmentSuffix(parenthetical[1])) {
    text = parenthetical[1]
  }

  const firstSegment = text.split(/[-—–_]/, 1)[0]
  if (DIRECT_ALIASES[firstSegment] || hasDepartmentSuffix(firstSegment)) {
    text = firstSegment
  }

  const aliasKey = text.toLocaleUpperCase()
  if (aliasKey.startsWith('客服')) return '客服部'
  return DIRECT_ALIASES[aliasKey] || text
}

export const departmentGroup = (value, fallback = OTHER_DEPARTMENT) => {
  const normalized = normalizeDepartment(value, fallback)
  return STANDARD_DEPARTMENTS.includes(normalized) ? normalized : fallback
}

export const departmentFromProjectName = (name) => {
  const text = String(name ?? '').trim()
  if (!/[-—–_]/.test(text)) return OTHER_DEPARTMENT
  return departmentGroup(text.split(/[-—–_]/, 1)[0])
}
