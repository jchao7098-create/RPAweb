// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LearningStats from './LearningStats.vue'

const api = vi.hoisted(() => ({
  fetchWeeklyStats: vi.fn(),
  fetchUserTrend: vi.fn(),
  fetchUserLearningHistory: vi.fn(),
  loadLearningProfile: vi.fn(),
  returnLearningReport: vi.fn(),
}))
vi.mock('@/api/learning', () => api)

describe('LearningStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.loadLearningProfile.mockResolvedValue({ can_manage_learning: true })
    api.fetchWeeklyStats.mockResolvedValue({
      week_start: '2026-07-20', submitted_count: 2, unsubmitted_count: 1,
      total_program_count: 3, average_completion: 75,
      rows: [{
        user_id: 8, username: 'intern', state: 'submitted', certificate: '中级',
        program_count: 1, completion: 70, record_date: '2026-07-23',
        can_return: true, report_id: 4,
      }],
    })
    api.fetchUserTrend.mockResolvedValue({ points: [{ week_start: '2026-07-20', program_count: 1, completion: 70 }] })
    api.fetchUserLearningHistory.mockResolvedValue({ items: [
      {
        submission_id: 12, report_id: 4, record_date: '2026-07-23', certificate: '中级',
        progress: 70, program_count: 1, blockers: '最新记录', state: 'submitted',
      },
      {
        submission_id: 11, report_id: 4, record_date: '2026-07-22', certificate: '初级',
        progress: 60, program_count: 0, blockers: '之前记录', state: 'submitted',
      },
    ] })
  })

  it('loads a selected user trend and collapses it on a second click', async () => {
    const wrapper = mount(LearningStats)
    await flushPromises()
    const row = wrapper.find('[data-test="roster-row"]')
    expect(wrapper.findAll('[data-test="kpi-card"]')).toHaveLength(4)

    await row.trigger('click')
    await flushPromises()
    expect(api.fetchUserTrend).toHaveBeenCalledWith(8, expect.any(Object))
    expect(api.fetchUserLearningHistory).toHaveBeenCalledWith(8)
    expect(wrapper.text()).toContain('intern 的趋势')
    expect(wrapper.find('[data-test="admin-progress-history"]').text()).toContain('2026/7/23')
    expect(wrapper.find('[data-test="admin-progress-history"]').text()).toContain('2026/7/22')
    expect(wrapper.find('[data-test="admin-progress-history"]').text()).toContain('中级')
    expect(wrapper.find('[data-test="admin-progress-history"]').findAll('tbody tr')).toHaveLength(2)

    await row.trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('intern 的趋势')
    expect(api.fetchUserTrend).toHaveBeenCalledTimes(1)
    expect(api.fetchUserLearningHistory).toHaveBeenCalledTimes(1)
  })

  it('requires a return reason and future deadline', async () => {
    const wrapper = mount(LearningStats)
    await flushPromises()
    await wrapper.find('[data-test="return-report"]').trigger('click')
    await wrapper.find('[data-test="confirm-return"]').trigger('click')
    expect(api.returnLearningReport).not.toHaveBeenCalled()
  })

  it('hides report return from a read-only administrator', async () => {
    api.loadLearningProfile.mockResolvedValue({ can_manage_learning: false })
    const wrapper = mount(LearningStats)
    await flushPromises()
    expect(wrapper.find('[data-test="return-report"]').exists()).toBe(false)
  })

  it('shows report return to an HR or boss administrator', async () => {
    api.loadLearningProfile.mockResolvedValue({ can_manage_learning: true })
    const wrapper = mount(LearningStats)
    await flushPromises()
    expect(wrapper.find('[data-test="return-report"]').exists()).toBe(true)
  })
})
