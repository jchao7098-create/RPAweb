// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LearningReport from './LearningReport.vue'

const api = vi.hoisted(() => ({
  fetchCurrentReport: vi.fn(), saveCurrentDraft: vi.fn(), submitCurrentReport: vi.fn(),
  fetchReportHistory: vi.fn(), fetchSubmissionHistory: vi.fn(), fetchReport: vi.fn(),
  saveReturnedDraft: vi.fn(), submitReturnedReport: vi.fn(),
}))
vi.mock('@/api/learning', () => api)

const current = {
  week_start: '2026-07-20', state: 'submitted', is_editable: true, draft_revision: 3,
  record_date: '2026-07-23', certificate: '中级', progress: 60, program_count: 1,
  blockers: '选择器定位不稳定', has_unsubmitted_changes: true,
  latest_submission: {
    record_date: '2026-07-22', certificate: '中级', progress: 50,
    program_count: 1, blockers: '等待测试环境',
  },
}

describe('LearningReport', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.fetchCurrentReport.mockResolvedValue(current)
    api.fetchReportHistory.mockResolvedValue([])
    api.fetchSubmissionHistory.mockResolvedValue({ items: [] })
  })

  it('enables report fields and actions when the API marks the report editable', async () => {
    const wrapper = mount(LearningReport)
    await flushPromises()

    expect(wrapper.find('[data-test="record-date"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="certificate"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="program-count"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="blockers"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="save-draft"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-test="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('sends the server revision when saving a draft and keeps values on 422', async () => {
    api.saveCurrentDraft.mockRejectedValue({ response: { status: 422, data: { error: 'invalid program count' } } })
    const wrapper = mount(LearningReport)
    await flushPromises()
    await wrapper.find('[data-test="blockers"]').setValue('选择器需要优化')
    await wrapper.find('[data-test="save-draft"]').trigger('click')
    await flushPromises()
    expect(api.saveCurrentDraft).toHaveBeenCalledWith(expect.objectContaining({
      draft_revision: 3, blockers: '选择器需要优化',
    }))
    expect(wrapper.find('[data-test="blockers"]').element.value).toBe('选择器需要优化')
  })

  it('saves a first-time report before directly submitting the saved revision', async () => {
    const draft = {
      ...current, state: 'draft', draft_revision: 0, certificate: '', progress: null,
      program_count: null, blockers: '', latest_submission: null, has_unsubmitted_changes: false,
    }
    api.fetchCurrentReport.mockResolvedValueOnce(draft)
    api.saveCurrentDraft.mockResolvedValue({
      ...draft, draft_revision: 1, certificate: '初级', progress: 20,
      program_count: 2, blockers: '首次直接提交',
    })
    const wrapper = mount(LearningReport)
    await flushPromises()

    await wrapper.find('[data-test="record-date"]').setValue('2026-07-23')
    await wrapper.find('[data-test="certificate"]').setValue('初级')
    await wrapper.find('[data-test="progress"]').setValue('20')
    await wrapper.find('[data-test="program-count"]').setValue('2')
    await wrapper.find('[data-test="blockers"]').setValue('首次直接提交')
    await wrapper.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(api.saveCurrentDraft).toHaveBeenCalledWith(expect.objectContaining({
      draft_revision: 0, record_date: '2026-07-23', certificate: '初级',
      progress: 20, program_count: 2, blockers: '首次直接提交',
    }))
    expect(api.submitCurrentReport).toHaveBeenCalledWith({ draft_revision: 1 })
    expect(api.saveCurrentDraft.mock.invocationCallOrder[0]).toBeLessThan(api.submitCurrentReport.mock.invocationCallOrder[0])
  })

  it('saves later edits and submits the new revision instead of the previous formal content', async () => {
    api.saveCurrentDraft.mockResolvedValue({ ...current, draft_revision: 4, blockers: '更新后的学习卡点' })
    const wrapper = mount(LearningReport)
    await flushPromises()

    await wrapper.find('[data-test="blockers"]').setValue('更新后的学习卡点')
    await wrapper.find('[data-test="submit"]').trigger('click')
    await flushPromises()

    expect(api.saveCurrentDraft).toHaveBeenCalledWith(expect.objectContaining({
      draft_revision: 3, blockers: '更新后的学习卡点',
    }))
    expect(api.submitCurrentReport).toHaveBeenCalledWith({ draft_revision: 4 })
  })

  it('shows server unsubmitted changes and disables actions for a locked report', async () => {
    const wrapper = mount(LearningReport)
    await flushPromises()
    expect(wrapper.find('[data-test="unsubmitted-changes"]').exists()).toBe(true)
    api.fetchCurrentReport.mockResolvedValueOnce({ ...current, is_editable: false, state: 'return_expired' })
    const locked = mount(LearningReport)
    await flushPromises()
    expect(locked.find('[data-test="save-draft"]').attributes('disabled')).toBeDefined()
    expect(locked.find('[data-test="submit"]').attributes('disabled')).toBeDefined()
  })

  it('renders historical formal submissions in the screenshot column format', async () => {
    api.fetchSubmissionHistory.mockResolvedValue({ items: [
      {
        submission_id: 10,
        report_id: 9,
        record_date: '2026-04-17',
        certificate: '中级',
        progress: 3,
        program_count: 0,
        blockers: '财务部繁忙',
      },
      {
        submission_id: 11,
        report_id: 9,
        record_date: '2026-04-21',
        certificate: '中级',
        progress: 6,
        program_count: 0,
        blockers: '学习结算表',
      },
    ] })

    const wrapper = mount(LearningReport)
    await flushPromises()

    expect(wrapper.find('[data-test="progress-history"]').text()).toContain('2026/4/17')
    expect(wrapper.find('[data-test="progress-history"]').text()).toContain('2026/4/21')
    expect(wrapper.find('[data-test="progress-history"]').text()).toContain('已编/在编程序数')
    expect(wrapper.find('[data-test="progress-history"]').text()).toContain('财务部繁忙')
    expect(wrapper.find('[data-test="progress-history"]').findAll('tbody tr')).toHaveLength(2)
  })
})
