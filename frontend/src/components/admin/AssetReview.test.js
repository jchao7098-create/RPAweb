// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetReview from './AssetReview.vue'

const api = vi.hoisted(() => ({
  fetchAdminAssets: vi.fn(),
  approveAsset: vi.fn(),
  rejectAsset: vi.fn(),
}))
vi.mock('@/api/assets', () => api)

describe('AssetReview unified review UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.fetchAdminAssets.mockResolvedValue({
      data: {
        data: [{
          id: 1,
          asset_type: 'skill',
          name: '自动日报',
          department: '客服部',
          submitter: '员工',
          version: '1.0',
          file_name: 'daily.zip',
          status: '待审核',
          progress: 0,
          lifecycle_status: '在编',
        }],
      },
    })
    api.approveAsset.mockResolvedValue({ data: { message: '已通过' } })
  })

  it('uses the same stats, department group, table and row actions as RPA review', async () => {
    const wrapper = mount(AssetReview, { props: { fixedType: 'skill' } })
    await flushPromises()

    expect(wrapper.findAll('.admin-stat')).toHaveLength(5)
    expect(wrapper.find('.dept-group').exists()).toBe(true)
    expect(wrapper.find('.admin-table').exists()).toBe(true)
    expect(wrapper.findAll('.btn-mini')).toHaveLength(3)
    expect(wrapper.text()).toContain('客服部')
    expect(wrapper.text()).toContain('审核进度')
  })

  it('approves a pending asset from the unified row action', async () => {
    const wrapper = mount(AssetReview, { props: { fixedType: 'skill' } })
    await flushPromises()
    await wrapper.find('.btn-mini-green').trigger('click')
    await flushPromises()

    expect(api.approveAsset).toHaveBeenCalledWith({ id: 1, apiPrefix: '/admin' })
    expect(wrapper.text()).toContain('已通过')
  })

  it('uses the signed user-management endpoints in the unified user workspace', async () => {
    const wrapper = mount(AssetReview, {
      props: { fixedType: 'skill', apiPrefix: '/user/manage' },
    })
    await flushPromises()

    expect(api.fetchAdminAssets).toHaveBeenCalledWith({
      assetType: 'skill',
      apiPrefix: '/user/manage',
    })

    await wrapper.find('.btn-mini-green').trigger('click')
    await flushPromises()
    expect(api.approveAsset).toHaveBeenCalledWith({
      id: 1,
      apiPrefix: '/user/manage',
    })
  })
})
