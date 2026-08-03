// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UserView from './UserView.vue'

const api = vi.hoisted(() => ({ loadLearningProfile: vi.fn() }))
vi.mock('@/api/learning', () => api)

const ConsoleShell = {
  props: {
    sections: Array,
    sectionGroups: Array,
  },
  template: '<div><span v-for="section in sections" :key="section.path">{{ section.label }}</span></div>',
}

describe('UserView learning navigation', () => {
  it('orders the main user sections by the daily workflow', async () => {
    api.loadLearningProfile.mockResolvedValue({})
    const wrapper = mount(UserView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()

    expect(wrapper.findAll('span').map((item) => item.text())).toEqual([
      '项目进度',
      '上传RPA程序',
      '上传 Skill',
      '上传插件',
      '维护记录',
      '需求审核',
      '开发进度管理',
      '维护管理',
      '数据导出',
    ])
    expect(wrapper.findComponent(ConsoleShell).props('sectionGroups').map((group) => group.label)).toEqual([
      '进度与记录',
      '提交中心',
      '审核与管理',
      '数据与学习',
    ])
    expect(wrapper.findComponent(ConsoleShell).props('enableSectionSearch')).toBeUndefined()
  })

  it('shows the RPA learning record entry to an eligible intern', async () => {
    api.loadLearningProfile.mockResolvedValue({ can_view_learning_report: true })
    const wrapper = mount(UserView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()
    expect(wrapper.text()).toContain('RPA 学习情况记录')
  })
})
