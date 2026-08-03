// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PublicView from './PublicView.vue'

const http = vi.hoisted(() => ({ get: vi.fn() }))
const assetApi = vi.hoisted(() => ({ fetchPublicAssets: vi.fn() }))

vi.mock('@/api/http', () => ({ default: http }))
vi.mock('@/api/assets', () => assetApi)

describe('PublicView hybrid homepage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    global.ResizeObserver = class {
      observe() {}
      disconnect() {}
    }
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      setTransform: vi.fn(),
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      fillText: vi.fn(),
      createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
      fillStyle: '',
    }))

    http.get.mockImplementation((url) => {
      if (url === '/public/projects') {
        return Promise.resolve({
          data: {
            data: [
              { id: 1, name: '客服部-RPA 日报', progress: 50, status: '在编' },
              { id: 2, name: '项目部-RPA 周报', progress: 100, status: '大修' },
            ],
          },
        })
      }
      return Promise.resolve({ data: [{ id: 7, status: '已通过' }] })
    })
    assetApi.fetchPublicAssets.mockImplementation(({ assetType }) => {
      if (assetType === 'skill') {
        return Promise.resolve({
          data: {
            data: [{
              id: 3,
              name: '客服质检 Skill',
              department: '客服部',
              progress: 20,
              lifecycle_status: '在编',
            }],
          },
        })
      }
      return Promise.resolve({
        data: {
          data: [{
            id: 4,
            name: '数据清洗 Python',
            department: '项目部',
            progress: 80,
            lifecycle_status: '使用',
          }],
        },
      })
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the original hero while preserving the improved homepage features', async () => {
    const wrapper = mount(PublicView, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.hero-title').text()).toContain('让 AI 与机器人')
    expect(wrapper.find('.hero-title').text()).toContain('接管重复工作')
    expect(wrapper.text()).toContain('RPA 机器人、Skill 文件、Python 插件，全生命周期一站式管理。')
    expect(wrapper.text()).toContain('查看项目进度')
    expect(wrapper.text()).toContain('提交需求')
    expect(wrapper.findAll('.sphere-count').map((node) => node.text())).toEqual(['2', '1', '1'])

    const navigation = wrapper.find('.nav')
    expect(navigation.text()).toContain('进入工作台')
    expect(navigation.text()).not.toContain('用户端入口')
    expect(navigation.text()).not.toContain('管理员入口')

    expect(wrapper.find('.total-card .stat-num').text()).toBe('4')
    expect(wrapper.findAll('.resource-card')).toHaveLength(3)
    expect(wrapper.find('.overview-grid').exists()).toBe(true)
    expect(wrapper.find('.progress-overview').exists()).toBe(true)
    expect(wrapper.find('.project-directory').exists()).toBe(true)
    expect(wrapper.find('.requirement-overview').exists()).toBe(true)
    expect(wrapper.findAll('.project-id').map((node) => node.text())).toEqual(
      expect.arrayContaining(['RPA #1', 'Skill #3', 'Python #4'])
    )
    expect(wrapper.findAll('.dept-name').map((node) => node.text())).toContain('客服部')
    expect(wrapper.findAll('.status-item').map((node) => node.text())).toEqual([
      '在编2',
      '使用1',
      '大修1',
      '停用0',
      '已通过需求1',
    ])
    expect(assetApi.fetchPublicAssets).toHaveBeenCalledWith({ assetType: 'skill' })
    expect(assetApi.fetchPublicAssets).toHaveBeenCalledWith({ assetType: 'python_plugin' })

    wrapper.unmount()
  })
})
