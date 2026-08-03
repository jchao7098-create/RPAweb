import { describe, expect, it } from 'vitest'
import { departmentFromProjectName, normalizeDepartment } from './departments'

describe('department normalization', () => {
  it('merges aliases and project text into one department', () => {
    expect(normalizeDepartment('客服')).toBe('客服部')
    expect(normalizeDepartment('客服部-售后-消息触达')).toBe('客服部')
    expect(normalizeDepartment('供应链')).toBe('供应链部')
    expect(normalizeDepartment('运营A组（杏花楼）')).toBe('运营A组')
  })

  it('normalizes the department segment of an RPA project name', () => {
    expect(departmentFromProjectName('客服-RPA回访')).toBe('客服部')
    expect(departmentFromProjectName('无部门信息')).toBe('其他')
  })
})
