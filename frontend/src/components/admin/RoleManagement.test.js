// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RoleManagement from './RoleManagement.vue'

const api = vi.hoisted(() => ({ fetchLearningUsers: vi.fn(), changeLearningRole: vi.fn(), fetchRoleChangeLogs: vi.fn() }))
vi.mock('@/api/learning', () => api)

describe('RoleManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.fetchLearningUsers.mockResolvedValue({ items: [{ user_id: 3, username: 'worker', role: 'employee' }], total: 1 })
    api.fetchRoleChangeLogs.mockResolvedValue({ items: [{ target_username: 'worker', operator_username: 'boss', old_role: 'employee', new_role: 'intern', changed_at: '2026-07-20T08:00:00' }], total: 1 })
  })

  it('shows all four roles and does not PATCH a same-role selection', async () => {
    const wrapper = mount(RoleManagement)
    await flushPromises()
    expect(wrapper.findAll('[data-test="role-option"]')).toHaveLength(4)
    await wrapper.find('[data-test="role-select"]').setValue('employee')
    expect(api.changeLearningRole).not.toHaveBeenCalled()
  })

  it('uses search params and shows audit target/operator/role fields', async () => {
    const wrapper = mount(RoleManagement)
    await flushPromises()
    await wrapper.find('[data-test="user-search"]').setValue('work')
    await wrapper.vm.searchNow()
    expect(api.fetchLearningUsers).toHaveBeenLastCalledWith(expect.objectContaining({ query: 'work' }))
    expect(wrapper.text()).toContain('worker')
    expect(wrapper.text()).toContain('boss')
  })
})
