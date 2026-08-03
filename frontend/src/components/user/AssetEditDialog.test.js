// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetEditDialog from './AssetEditDialog.vue'

const api = vi.hoisted(() => ({ updateMyAsset: vi.fn() }))
const message = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))

vi.mock('@/api/assets', () => api)
vi.mock('element-plus/es', async (importOriginal) => ({
  ...(await importOriginal()),
  ElMessage: message,
}))
vi.mock('element-plus/es/components/message/style/css', () => ({}))
vi.mock('element-plus/es/components/message/style/css.mjs', () => ({}))
vi.mock('element-plus/theme-chalk/base.css', () => ({}))

describe('AssetEditDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.updateMyAsset.mockResolvedValue({
      data: {
        message: '修改已提交，等待管理员重新审核',
        data: {
          id: 3,
          name: '客服部-新名称-skill',
          status: '待审核',
          progress: 0,
          lifecycle_status: '在编',
        },
      },
    })
  })

  it('submits corrected asset information for re-review', async () => {
    const wrapper = mount(AssetEditDialog, {
      props: {
        modelValue: true,
        assetTypeId: 'skill',
        userId: '7',
        asset: {
          id: 3,
          name: '旧名称',
          department: '客服部',
          submitter: '张三',
          version: '1.0',
          description: '原始说明',
          file_name: 'old.zip',
          status: '已通过',
        },
      },
    })
    await flushPromises()

    await wrapper.get('[data-test="edit-name"]').setValue('客服部-新名称-skill')
    await wrapper.get('[data-test="save-asset-edit"]').trigger('click')
    await flushPromises()

    expect(api.updateMyAsset).toHaveBeenCalledWith({
      id: 3,
      userId: '7',
      name: '客服部-新名称-skill',
      department: '客服部',
      submitter: '张三',
      version: '1.0',
      description: '原始说明',
      fileName: 'old.zip',
    })
    expect(wrapper.emitted('saved')[0][0]).toMatchObject({
      id: 3,
      status: '待审核',
      progress: 0,
    })
  })
})
