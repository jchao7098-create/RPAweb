const DIRECT_ALIASES = {
  客服: '客服部',
  客服部门: '客服部',
  客服组: '客服部',
  人事: '人事部',
  人事部门: '人事部',
  供应链: '供应链部',
  供应链部门: '供应链部',
  市场: '市场部',
  市场部门: '市场部',
  财务: '财务部',
  财务部门: '财务部',
  行政: '行政部',
  行政部门: '行政部',
  项目: '项目部',
  项目部门: '项目部',
  运营A: '运营A组',
}

const DEPARTMENT_SUFFIXES = ['部', '组', '中心', '室', '科']
const hasDepartmentSuffix = (value) =>
  DEPARTMENT_SUFFIXES.some((suffix) => value.endsWith(suffix))

export const normalizeDepartment = (value, fallback = '未指定部门') => {
  let text = String(value ?? '').trim().replace(/\s+/g, '')
  if (!text) return fallback

  const parenthetical = text.match(/^(.+?)[（(][^）)]*[）)]$/)
  if (parenthetical && hasDepartmentSuffix(parenthetical[1])) {
    text = parenthetical[1]
  }

  const firstSegment = text.split(/[-—–_]/, 1)[0]
  if (DIRECT_ALIASES[firstSegment] || hasDepartmentSuffix(firstSegment)) {
    text = firstSegment
  }

  if (text.startsWith('客服')) return '客服部'
  return DIRECT_ALIASES[text] || text
}

export const departmentFromProjectName = (name) => {
  const text = String(name ?? '').trim()
  if (!/[-—–_]/.test(text)) return '其他'
  return normalizeDepartment(text.split(/[-—–_]/, 1)[0], '其他')
}
