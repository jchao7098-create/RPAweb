// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RpaRequirement from './RpaRequirement.vue'

const api = vi.hoisted(() => ({
  post: vi.fn(),
  fetchMyRequirements: vi.fn(),
  updateMyRequirement: vi.fn(),
}))
const message = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}))

vi.mock('@/api/http', () => ({ default: { post: api.post } }))
vi.mock('@/api/requirements', () => ({
  fetchMyRequirements: api.fetchMyRequirements,
  updateMyRequirement: api.updateMyRequirement,
}))
vi.mock('element-plus/es', async (importOriginal) => ({
  ...(await importOriginal()),
  ElMessage: message,
}))

const ownRequirement = {
  id: 31,
  title: '客服部-售后数据获取-日报',
  department: '客服部',
  requester: '小王',
  priority: '高',
  status: '待审核',
  created_at: '2026-07-30 10:20',
  editable: true,
}

describe('RpaRequirement own uploads', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('user_id', '7')
    api.fetchMyRequirements.mockResolvedValue({
      data: { data: [ownRequirement] },
    })
    api.post.mockResolvedValue({ data: { message: '需求提交成功' } })
  })

  it('loads and displays only the signed-in user upload records', async () => {
    const wrapper = mount(RpaRequirement, {
      global: { stubs: { RequirementEditDialog: true } },
    })
    await flushPromises()

    expect(api.fetchMyRequirements).toHaveBeenCalledWith('7')
    expect(wrapper.text()).toContain('我上传的 RPA 程序')
    expect(wrapper.text()).toContain('提交 #31')
    expect(wrapper.text()).toContain('客服部-售后数据获取-日报')
    expect(wrapper.text()).toContain('待审核')
  })

  it('refreshes the own-upload list after a successful submission', async () => {
    const newRequirement = {
      ...ownRequirement,
      id: 32,
      title: '客服部-售后数据同步-日报',
    }
    api.fetchMyRequirements
      .mockResolvedValueOnce({ data: { data: [ownRequirement] } })
      .mockResolvedValueOnce({ data: { data: [newRequirement, ownRequirement] } })

    const wrapper = mount(RpaRequirement, {
      global: { stubs: { RequirementEditDialog: true } },
    })
    await flushPromises()

    const state = wrapper.vm.$.setupState
    state.form.title = newRequirement.title
    state.form.requester = '小王'
    const submitButton = wrapper.findAll('button').find(
      (button) => button.text().includes('提交需求')
    )
    await submitButton.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledOnce()
    expect(api.fetchMyRequirements).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('提交 #32')
    expect(wrapper.text()).toContain(newRequirement.title)
  })

  it('does not request records when no user is logged in', async () => {
    localStorage.removeItem('user_id')
    mount(RpaRequirement, {
      global: { stubs: { RequirementEditDialog: true } },
    })
    await flushPromises()

    expect(api.fetchMyRequirements).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith('请先登录')
  })
})
