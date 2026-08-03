// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import LearningTrendChart from './LearningTrendChart.vue'

describe('LearningTrendChart', () => {
  it('renders bars only for submitted program counts and a progress line', () => {
    const wrapper = mount(LearningTrendChart, { props: { points: [
      { week_start: '2026-07-06', program_count: 0, completion: 50 },
      { week_start: '2026-07-13', program_count: null, completion: null },
      { week_start: '2026-07-20', program_count: 2, completion: 80 },
    ] } })
    expect(wrapper.findAll('[data-test="program-bar"]')).toHaveLength(2)
    expect(wrapper.findAll('[data-test="program-label"]')).toHaveLength(2)
    expect(wrapper.find('[data-test="completion-line"]').attributes('points')).toContain(',')
  })

  it('scales program-count bars and labels each value', () => {
    const wrapper = mount(LearningTrendChart, { props: { points: [
      { week_start: '2026-07-13', program_count: 1, completion: 50 },
      { week_start: '2026-07-20', program_count: 2, completion: 80 },
    ] } })

    const bars = wrapper.findAll('[data-test="program-bar"]')
    expect(Number(bars[0].attributes('height'))).toBeCloseTo(100)
    expect(Number(bars[1].attributes('height'))).toBeCloseTo(200)
    expect(wrapper.findAll('[data-test="program-label"]').map((label) => label.text())).toEqual(['1 个', '2 个'])
  })

  it('offers an accessible empty state', () => {
    const wrapper = mount(LearningTrendChart, { props: { points: [] } })
    expect(wrapper.find('[data-test="trend-empty"]').attributes('role')).toBe('img')
  })
})
