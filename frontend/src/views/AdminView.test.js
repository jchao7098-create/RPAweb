// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminView from './AdminView.vue'

const api = vi.hoisted(() => ({ loadLearningProfile: vi.fn() }))
vi.mock('@/api/learning', () => api)

const ConsoleShell = {
  props: ['sections'],
  template: '<div><span v-for="section in sections" :key="section.path">{{ section.label }}</span></div>',
}

describe('AdminView learning navigation', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows stats but not role management to a read-only admin', async () => {
    api.loadLearningProfile.mockResolvedValue({
      can_view_learning_stats: true,
      can_manage_learning: false,
    })
    const wrapper = mount(AdminView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()
    expect(wrapper.text()).toContain('学习统计')
    expect(wrapper.text()).not.toContain('人员权限')
  })

  it('shows both entries to an HR or boss admin', async () => {
    api.loadLearningProfile.mockResolvedValue({
      can_view_learning_stats: true,
      can_manage_learning: true,
    })
    const wrapper = mount(AdminView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()
    expect(wrapper.text()).toContain('学习统计')
    expect(wrapper.text()).toContain('人员权限')
  })
})
