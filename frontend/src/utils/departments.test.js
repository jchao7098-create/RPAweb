import { describe, expect, it } from 'vitest'
import {
  DEPARTMENT_OPTIONS,
  departmentFromProjectName,
  departmentGroup,
  normalizeDepartment,
} from './departments'

describe('department normalization', () => {
  it('merges aliases and project text into one department', () => {
    expect(normalizeDepartment('客服')).toBe('客服部')
    expect(normalizeDepartment('客服部-售后-消息触达')).toBe('客服部')
    expect(normalizeDepartment('供应链')).toBe('供应链部')
    expect(normalizeDepartment('运营A组（杏花楼）')).toBe('运营A组')
    expect(normalizeDepartment('运营e组')).toBe('运营E组')
    expect(normalizeDepartment('E组')).toBe('运营E组')
    expect(normalizeDepartment('人事部')).toBe('人事行政部')
    expect(normalizeDepartment('行政部')).toBe('人事行政部')
  })

  it('exposes the configured department choices and groups custom values as other', () => {
    expect(DEPARTMENT_OPTIONS.map((item) => item.label)).toEqual([
      '运营A组',
      '运营E组',
      '项目部',
      '客服部',
      '财务部',
      '供应链部',
      '人事行政部',
      'AI应用部',
      '其他（可编辑）',
    ])
    expect(departmentGroup('市场部')).toBe('其他')
  })

  it('normalizes the department segment of an RPA project name', () => {
    expect(departmentFromProjectName('客服-RPA回访')).toBe('客服部')
    expect(departmentFromProjectName('无部门信息')).toBe('其他')
  })
})
