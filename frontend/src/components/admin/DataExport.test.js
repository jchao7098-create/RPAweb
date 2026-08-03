// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DataExport from './DataExport.vue'

const http = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: http }))

describe('DataExport learning report', () => {
  let clickAnchor

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-22T04:00:00Z'))
    http.get.mockReset()
    http.get.mockResolvedValue({ data: new Blob(['csv']) })
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:learning'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
    clickAnchor = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    vi.stubGlobal('ElMessage', { success: vi.fn(), error: vi.fn() })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('downloads all historical intern learning data from the selected platform endpoint', async () => {
    const wrapper = mount(DataExport, { props: { apiPrefix: '/user/manage' } })
    const button = wrapper.find('[data-test="learning-export"]')
    expect(button.exists()).toBe(true)

    await button.trigger('click')
    await flushPromises()

    expect(http.get).toHaveBeenCalledWith('/user/manage/export/intern_learning', { responseType: 'blob' })
    const clickedAnchor = clickAnchor.mock.contexts[0]
    expect(clickedAnchor.download).toBe('实习生RPA学习全部数据_2026-07-22.csv')
    expect(wrapper.text()).toContain('所有统计周')
  })

  it('downloads one ZIP containing the complete platform datasets', async () => {
    const wrapper = mount(DataExport, { props: { apiPrefix: '/user/manage' } })

    await wrapper.find('[data-test="full-export"]').trigger('click')
    await flushPromises()

    expect(http.get).toHaveBeenCalledWith('/user/manage/export/full_archive', { responseType: 'blob' })
    const clickedAnchor = clickAnchor.mock.contexts[0]
    expect(clickedAnchor.download).toBe('AI_Tools全平台数据_2026-07-22.zip')
    expect(wrapper.text()).toContain('实习生全部学习周报')
    expect(wrapper.text()).toContain('不导出网站密码')
  })
})
