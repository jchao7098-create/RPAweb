// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import DepartmentAssets from './DepartmentAssets.vue'

const api = vi.hoisted(() => ({ fetchPublicAssets: vi.fn() }))
vi.mock('@/api/assets', () => api)

describe('DepartmentAssets search', () => {
  it('filters Skill/Python assets by department and asset metadata', async () => {
    api.fetchPublicAssets.mockResolvedValue({
      data: {
        data: [
          {
            id: 1,
            name: '工单自动分类',
            department: '客服部',
            submitter: '小张',
            version: '1.0',
            file_name: 'ticket.md',
            status: '已通过',
            lifecycle_status: '使用',
            progress: 100,
          },
          {
            id: 2,
            name: '项目数据整理',
            department: '项目部',
            submitter: '小李',
            version: '2.0',
            file_name: 'project.md',
            status: '已通过',
            lifecycle_status: '在编',
            progress: 30,
          },
        ],
      },
    })
    const wrapper = mount(DepartmentAssets, {
      props: { assetTypeId: 'skill' },
      global: { stubs: { RouterLink: true } },
    })
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('Skill 文件 #1')

    await wrapper.get('[data-test="department-asset-search"]').setValue('2')

    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('项目数据整理')
    expect(wrapper.text()).toContain('Skill 文件 #2')
    expect(wrapper.text()).not.toContain('工单自动分类')
    expect(wrapper.text()).toContain('找到 1 个，共 2 个')
  })
})
