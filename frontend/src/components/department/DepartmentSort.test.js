// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import DepartmentSort from './DepartmentSort.vue'

const http = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: http }))

describe('DepartmentSort search', () => {
  it('filters RPA requirements and project statistics with one keyword', async () => {
    http.get.mockImplementation((path) => {
      if (path === '/public/projects') {
        return Promise.resolve({
          data: {
            data: [
              { id: 1, name: '客服-RPA回访', status: '在编', logs: [] },
              { id: 2, name: '项目部-数据同步', status: '使用', logs: [] },
            ],
          },
        })
      }
      return Promise.resolve({
        data: [
          {
            id: 1,
            title: '客服日报',
            department: '客服',
            requester: '小张',
            status: '待审核',
            expected_time: '2026-08-01 18:00:00',
          },
          {
            id: 2,
            title: '项目数据同步',
            department: '项目部',
            requester: '小李',
            status: '已通过',
            expected_time: '2026-08-05 18:00:00',
          },
        ],
      })
    })
    const wrapper = mount(DepartmentSort, {
      global: { stubs: { RouterLink: true } },
    })
    await flushPromises()

    expect(wrapper.findAll('[data-test="rpa-project-table"] tbody tr')).toHaveLength(2)
    expect(wrapper.findAll('[data-test="rpa-requirement-table"] tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('RPA #1')

    await wrapper.get('[data-test="department-rpa-search"]').setValue('客服')

    expect(wrapper.findAll('[data-test="rpa-project-table"] tbody tr')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="rpa-requirement-table"] tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('客服日报')
    expect(wrapper.text()).not.toContain('项目数据同步')
    expect(wrapper.text()).toContain('需求 1/2，项目 1/2')
  })
})
