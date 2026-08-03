// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ConsoleShell from './ConsoleShell.vue'

const sections = [
  {
    path: '/main/RpaProgress',
    label: '项目进度',
    desc: '查看开发进展日志',
    group: 'tracking',
  },
  {
    path: '/main/RpaMaintance',
    label: '维护记录',
    desc: '查看历史维护工单',
    group: 'tracking',
  },
  {
    path: '/main/SkillUpload',
    label: '上传 Skill',
    desc: '登记 Skill 文件资产',
    group: 'submission',
  },
]

describe('ConsoleShell navigation', () => {
  it('keeps the user navigation without the removed top search field', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/main', component: { template: '<div />' } },
        { path: '/main/:page', component: { template: '<div />' } },
      ],
    })
    await router.push('/main/RpaProgress')
    await router.isReady()

    const wrapper = mount(ConsoleShell, {
      props: {
        roleLabel: '用户端',
        sections,
        sectionGroups: [
          { key: 'tracking', label: '进度与记录' },
          { key: 'submission', label: '提交中心' },
        ],
        welcomeTitle: '用户工作台',
        welcomeSub: '选择栏目',
        rootPath: '/main',
        backLabel: '回到用户工作台',
      },
      global: { plugins: [router] },
    })

    expect(wrapper.find('#console-section-search-input').exists()).toBe(false)
    expect(wrapper.find('.console-section-search').exists()).toBe(false)
    expect(wrapper.findAll('.console-nav-links a').map((link) => link.text())).toEqual([
      '项目进度',
      '维护记录',
      '上传 Skill',
    ])
  })

  it('shows directional controls only for overflowing navigation and updates their edge states', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/main', component: { template: '<div />' } },
        { path: '/main/:page', component: { template: '<div />' } },
      ],
    })
    await router.push('/main/RpaProgress')
    await router.isReady()

    const wrapper = mount(ConsoleShell, {
      props: {
        roleLabel: '用户端',
        sections,
        welcomeTitle: '用户工作台',
        welcomeSub: '选择栏目',
        rootPath: '/main',
        backLabel: '回到用户工作台',
      },
      global: { plugins: [router] },
    })

    const navigation = wrapper.get('#console-primary-navigation')
    const left = wrapper.get('button[aria-label="向左查看更多功能"]')
    const right = wrapper.get('button[aria-label="向右查看更多功能"]')
    expect(left.attributes('style')).toContain('display: none')
    expect(right.attributes('style')).toContain('display: none')
    expect(navigation.attributes('tabindex')).toBe('-1')

    Object.defineProperties(navigation.element, {
      clientWidth: { configurable: true, value: 300 },
      scrollWidth: { configurable: true, value: 900 },
    })
    navigation.element.scrollBy = vi.fn()
    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(left.attributes('style')).not.toContain('display: none')
    expect(right.attributes('style')).not.toContain('display: none')
    expect(navigation.attributes('tabindex')).toBe('0')
    expect(left.attributes('disabled')).toBeDefined()
    expect(right.attributes('disabled')).toBeUndefined()

    await right.trigger('click')
    expect(navigation.element.scrollBy).toHaveBeenCalledWith({
      left: 216,
      behavior: 'smooth',
    })

    navigation.element.scrollLeft = 300
    await navigation.trigger('scroll')
    expect(left.attributes('disabled')).toBeUndefined()
    expect(right.attributes('disabled')).toBeUndefined()
    await left.trigger('click')
    expect(navigation.element.scrollBy).toHaveBeenLastCalledWith({
      left: -216,
      behavior: 'smooth',
    })

    navigation.element.scrollLeft = 600
    await navigation.trigger('scroll')
    expect(left.attributes('disabled')).toBeUndefined()
    expect(right.attributes('disabled')).toBeDefined()

    navigation.element.scrollLeft = 0
    Object.defineProperty(navigation.element, 'scrollWidth', {
      configurable: true,
      value: 300,
    })
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    await nextTick()
    expect(left.attributes('style')).toContain('display: none')
    expect(right.attributes('style')).toContain('display: none')
    expect(navigation.attributes('tabindex')).toBe('-1')

    wrapper.unmount()
  })
})
