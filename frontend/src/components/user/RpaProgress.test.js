// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RpaProgress from './RpaProgress.vue'

const api = vi.hoisted(() => ({
  get: vi.fn(),
  fetchMyAssets: vi.fn(),
  fetchAdminAssets: vi.fn(),
  updateAssetProgress: vi.fn(),
}))

vi.mock('@/api/http', () => ({ default: { get: api.get } }))
vi.mock('@/api/assets', () => ({
  fetchMyAssets: api.fetchMyAssets,
  fetchAdminAssets: api.fetchAdminAssets,
  updateAssetProgress: api.updateAssetProgress,
}))

describe('RpaProgress summary navigation', () => {
  beforeEach(() => {
    localStorage.setItem('user_id', '7')
    api.get.mockReset()
    api.fetchMyAssets.mockReset()
    api.get.mockResolvedValue({ data: { data: [] } })
    api.fetchMyAssets.mockResolvedValue({ data: { data: [] } })
    api.fetchAdminAssets.mockResolvedValue({ data: { data: [] } })
  })

  it('scrolls every summary card to its matching detail section', async () => {
    const wrapper = mount(RpaProgress, {
      attachTo: document.body,
      global: {
        stubs: {
          AssetEditDialog: true,
        },
      },
    })
    await flushPromises()

    const mappings = [
      ['查看我的需求明细', 'requirements-details'],
      ['查看非使用状态项目明细', 'active-projects-details'],
      ['查看已完成项目明细', 'completed-projects-details'],
      ['查看维护任务明细', 'maintenance-details'],
      ['查看 Skill 提交明细', 'skill-details'],
      ['查看插件提交明细', 'plugin-details'],
    ]

    for (const [label, targetId] of mappings) {
      const target = wrapper.get(`#${targetId}`).element
      target.scrollIntoView = vi.fn()

      await wrapper.get(`button[aria-label="${label}"]`).trigger('click')

      expect(target.scrollIntoView).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'start',
      })
    }

    wrapper.unmount()
  })

  it('groups projects by the latest status returned by the API, not progress', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/user/get_my_projects') {
        return Promise.resolve({
          data: {
            data: [
              { id: 1, name: '满进度大修项目', progress: 100, status: '大修', logs: [] },
              { id: 2, name: '低进度使用项目', progress: 10, status: '使用', logs: [] },
            ],
          },
        })
      }
      return Promise.resolve({ data: { data: [] } })
    })

    const wrapper = mount(RpaProgress, {
      global: { stubs: { AssetEditDialog: true } },
    })
    await flushPromises()

    expect(wrapper.get('#active-projects-details').text()).toContain('满进度大修项目')
    expect(wrapper.get('#active-projects-details').text()).not.toContain('低进度使用项目')
    expect(wrapper.get('#completed-projects-details').text()).toContain('低进度使用项目')
    expect(wrapper.get('#completed-projects-details').text()).not.toContain('满进度大修项目')
  })

  it('slides between personal and company views and refreshes from shared data', async () => {
    const wrapper = mount(RpaProgress, {
      global: {
        stubs: {
          AssetEditDialog: true,
          RequirementEditDialog: true,
        },
      },
    })
    await flushPromises()

    const companyButton = wrapper.findAll('.progress-scope-switch button').find(
      (button) => button.text() === '全公司版'
    )
    await companyButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('全公司项目进度')
    expect(wrapper.find('.progress-scope-thumb').classes()).toContain('is-company')
    expect(api.get).toHaveBeenCalledWith('/user/manage/get_projects', {
      params: { scope: 'all' },
    })
    expect(api.fetchAdminAssets).toHaveBeenCalledWith({
      apiPrefix: '/user/manage',
      scope: 'all',
    })

    const personalButton = wrapper.findAll('.progress-scope-switch button').find(
      (button) => button.text() === '个人版'
    )
    await personalButton.trigger('click')
    await flushPromises()

    const ownRequests = api.get.mock.calls.filter(
      ([url]) => url === '/user/get_my_requirements'
    )
    expect(ownRequests).toHaveLength(2)
    expect(wrapper.text()).toContain('我的需求')
  })
})
