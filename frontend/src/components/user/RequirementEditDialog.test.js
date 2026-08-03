// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RequirementEditDialog from './RequirementEditDialog.vue'

const api = vi.hoisted(() => ({ updateMyRequirement: vi.fn() }))
const message = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))

vi.mock('@/api/requirements', () => api)
vi.mock('element-plus/es', async (importOriginal) => ({
  ...(await importOriginal()),
  ElMessage: message,
}))

const requirement = {
  id: 12,
  title: '客服部-日报',
  description: '原需求',
  department: '客服部',
  requester: '小王',
  priority: '中',
  feedback_time: '2026-07-28 09:00:00',
  expected_finish_time: '2026-08-15 18:00:00',
  platform: '浏览器',
  operation_link: 'https://example.com',
  account: 'tester',
  status: '已拒绝',
  editable: true,
}

describe('RequirementEditDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.updateMyRequirement.mockResolvedValue({
      data: {
        message: '需求已更新，等待重新审核',
        data: { ...requirement, title: '客服部-日报修订', status: '待审核' },
      },
    })
  })

  it('updates an editable requirement and sends it back to review', async () => {
    const wrapper = mount(RequirementEditDialog, {
      props: {
        modelValue: true,
        requirement,
        userId: '7',
      },
    })
    await flushPromises()

    await wrapper.get('[data-test="requirement-title"]').setValue('客服部-日报修订')
    await wrapper.get('.el-dialog__footer .el-button--primary').trigger('click')
    await flushPromises()

    expect(api.updateMyRequirement).toHaveBeenCalledWith(expect.objectContaining({
      id: 12,
      userId: '7',
      title: '客服部-日报修订',
      priority: '中',
    }))
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({
      id: 12,
      status: '待审核',
    })
  })
})
