// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

const http = vi.hoisted(() => ({ post: vi.fn() }))
const router = vi.hoisted(() => ({ push: vi.fn() }))
const message = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock('@/api/http', () => ({ default: http }))
vi.mock('@/router', () => ({ default: router }))
vi.mock('element-plus/es', () => ({ ElMessage: message }))
vi.mock('element-plus/es/components/message/style/css', () => ({}))
vi.mock('element-plus/es/components/message/style/css.mjs', () => ({}))
vi.mock('element-plus/theme-chalk/base.css', () => ({}))
vi.mock('@/utils/credentialStore', () => ({
  getSavedPassword: vi.fn(() => ''),
  saveAccount: vi.fn(),
  removeAccount: vi.fn(),
}))

let LoginView

describe('LoginView position selection', () => {
  beforeAll(async () => {
    LoginView = (await import('./LoginView.vue')).default
  })

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    http.post.mockResolvedValue({ data: {
      message: '登录成功',
      user_id: 1,
      learning_token: 'signed',
      learning_role: 'intern',
    } })
  })

  it('shows and submits position for user login', async () => {
    const wrapper = mount(LoginView, {
      props: { audience: 'user' },
      global: { stubs: { RouterLink: true } },
    })
    await wrapper.get('input[type="text"]').setValue('worker')
    await wrapper.get('input[type="password"]').setValue('secret1')
    await wrapper.get('[data-test="employment-type"]').setValue('intern')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/user/login', {
      username: 'worker',
      password: 'secret1',
      employment_type: 'intern',
    })
  })

  it('does not render or send position for admin login', async () => {
    http.post.mockResolvedValue({ data: {
      message: '登录成功',
      admin_id: 1,
      learning_token: 'signed',
      learning_role: 'employee',
    } })
    const wrapper = mount(LoginView, {
      props: { audience: 'admin' },
      global: { stubs: { RouterLink: true } },
    })
    expect(wrapper.find('[data-test="employment-type"]').exists()).toBe(false)
    await wrapper.get('input[type="text"]').setValue('admin')
    await wrapper.get('input[type="password"]').setValue('secret1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/admin/login', {
      username: 'admin',
      password: 'secret1',
    })
  })

  it('shows the forgot-password entry on both login surfaces', () => {
    const userWrapper = mount(LoginView, {
      props: { audience: 'user' },
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="to"><slot /></a>',
          },
        },
      },
    })
    const adminWrapper = mount(LoginView, {
      props: { audience: 'admin' },
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="to"><slot /></a>',
          },
        },
      },
    })
    expect(userWrapper.get('.auth-option-link').attributes('data-to')).toBe('/forgot-password')
    expect(adminWrapper.get('.auth-option-link').attributes('data-to')).toBe('/admin-forgot-password')
  })
})
