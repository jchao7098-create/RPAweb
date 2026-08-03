// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest'
import {
  canManageLearning,
  canViewLearningStats,
  canViewReport,
  clearLearningSession,
  getLearningToken,
  setLearningSession,
} from './learningSession'

describe('learningSession', () => {
  beforeEach(() => localStorage.clear())

  it('stores and clears a learning token independently of the existing login session', () => {
    setLearningSession({ token: 'signed', role: 'intern' })
    expect(getLearningToken()).toBe('signed')
    clearLearningSession()
    expect(getLearningToken()).toBe('')
  })

  it('uses server capability flags rather than a cached role for access checks', () => {
    expect(canViewReport({ can_view_learning_report: true })).toBe(true)
    expect(canManageLearning({ can_manage_learning: true })).toBe(true)
    expect(canManageLearning({ role: 'boss' })).toBe(false)
  })

  it('separates statistics viewing from learning management', () => {
    expect(canViewLearningStats({ can_view_learning_stats: true })).toBe(true)
    expect(canViewLearningStats({ can_manage_learning: true })).toBe(false)
    expect(canManageLearning({ can_view_learning_stats: true })).toBe(false)
  })
})
