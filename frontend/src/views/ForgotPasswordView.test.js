// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({ post: vi.fn() }))
const message = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
const routeState = vi.hoisted(() => ({ query: {} }))
const removeAccount = vi.hoisted(() => vi.fn())

vi.mock('@/api/http', () => ({ default: http }))
vi.mock('@/utils/credentialStore', () => ({ removeAccount }))
vi.mock('vue-router', () => ({ useRoute: () => routeState }))
vi.mock('element-plus/es', () => ({ ElMessage: message }))
vi.mock('element-plus/es/components/message/style/css', () => ({}))
vi.mock('element-plus/es/components/message/style/css.mjs', () => ({}))
vi.mock('element-plus/theme-chalk/base.css', () => ({}))

let ForgotPasswordView

describe('ForgotPasswordView', () => {
  beforeAll(async () => {
    ForgotPasswordView = (await import('./ForgotPasswordView.vue')).default
  })

  beforeEach(() => {
    vi.clearAllMocks()
    routeState.query = {}
  })

  it('requests a reset link for the registered email', async () => {
    http.post.mockResolvedValue({
      data: { message: '如果该邮箱已注册，重置邮件会在几分钟内发送' },
    })
    const wrapper = mount(ForgotPasswordView, {
      props: { audience: 'user' },
      global: { stubs: { RouterLink: true } },
    })

    await wrapper.get('input[type="email"]').setValue('worker@example.com')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(http.post).toHaveBeenCalledWith('/user/password-reset/request', {
      email: 'worker@example.com',
      audience: 'user',
    })
    expect(wrapper.find('[data-test="request-success"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="registered-email-note"]').text()).toContain('未注册邮箱')
  })

  it('resets the password and clears remembered old passwords', async () => {
    routeState.query = { token: 'signed-token' }
    http.post.mockResolvedValue({
      data: {
        message: '密码已重置，请使用新密码登录',
        username: 'worker',
        email: 'worker@example.com',
      },
    })
    const wrapper = mount(ForgotPasswordView, {
      props: { audience: 'admin' },
      global: { stubs: { RouterLink: true } },
    })

    const passwordInputs = wrapper.findAll('input[type="password"]')
    await passwordInputs[0].setValue('new-secret')
    await passwordInputs[1].setValue('new-secret')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(http.post).toHaveBeenCalledWith('/user/password-reset/confirm', {
      token: 'signed-token',
      password: 'new-secret',
      confirm_password: 'new-secret',
    })
    expect(removeAccount).toHaveBeenCalledTimes(4)
    expect(removeAccount).toHaveBeenCalledWith('user', 'worker')
    expect(removeAccount).toHaveBeenCalledWith('admin', 'worker@example.com')
    expect(wrapper.find('[data-test="reset-success"]').exists()).toBe(true)
  })
})
