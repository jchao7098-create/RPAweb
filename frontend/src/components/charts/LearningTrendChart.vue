<script setup>
import { computed } from 'vue'

const props = defineProps({ points: { type: Array, default: () => [] } })
const width = 640
const height = 260
const padding = { left: 42, right: 42, top: 22, bottom: 38 }
const usableWidth = width - padding.left - padding.right
const usableHeight = height - padding.top - padding.bottom
const x = (index) => padding.left + (props.points.length < 2 ? usableWidth / 2 : index * usableWidth / (props.points.length - 1))
const programScaleMax = computed(() => Math.max(
  1,
  ...props.points.map((point) => Number(point.program_count) || 0),
))
const clampedPrograms = (count) => Math.min(programScaleMax.value, Math.max(0, Number(count) || 0))
const programY = (count) => padding.top + usableHeight - clampedPrograms(count) / programScaleMax.value * usableHeight
const programLabel = (count) => `${Number(count)} 个`
const programLabelY = (count) => Math.max(14, programY(count) - 6)
const completionY = (completion) => padding.top + usableHeight - Number(completion) / 100 * usableHeight
const completionPoints = computed(() => props.points
  .map((point, index) => point.completion == null ? null : `${x(index)},${completionY(point.completion)}`)
  .filter(Boolean).join(' '))
</script>

<template>
  <div v-if="!points.length" data-test="trend-empty" role="img" aria-label="暂无个人学习趋势数据" class="trend-empty">暂无趋势数据</div>
  <svg v-else class="trend-chart" :viewBox="`0 0 ${width} ${height}`" role="img" aria-label="程序数量柱状图与学习进度折线图">
    <line :x1="padding.left" :x2="width - padding.right" :y1="height - padding.bottom" :y2="height - padding.bottom" stroke="currentColor" opacity=".2" />
    <g v-for="(point, index) in points" :key="point.week_start || index">
      <rect v-if="point.program_count != null" data-test="program-bar" :x="x(index) - 10" :y="programY(point.program_count)" width="20" :height="height - padding.bottom - programY(point.program_count)" rx="3" fill="#7c5cff" />
      <text v-if="point.program_count != null" data-test="program-label" :x="x(index)" :y="programLabelY(point.program_count)" text-anchor="middle" class="program-value">{{ programLabel(point.program_count) }}</text>
      <circle v-if="point.completion != null" :cx="x(index)" :cy="completionY(point.completion)" r="4" fill="#ee7752" />
      <text :x="x(index)" :y="height - 14" text-anchor="middle" class="trend-label">{{ String(point.week_start || '').slice(5) }}</text>
    </g>
    <polyline data-test="completion-line" :points="completionPoints" fill="none" stroke="#ee7752" stroke-width="3" />
    <text :x="width - 32" :y="padding.top" class="trend-label">100%</text>
  </svg>
</template>

<style scoped>
.trend-chart { width: 100%; min-height: 230px; color: #303036; }
.trend-label { fill: #797982; font-size: 11px; }
.program-value { fill: #5d3ee8; font-size: 10px; font-weight: 700; }
.trend-empty { padding: 36px; color: var(--brand-muted); text-align: center; border: 1px dashed var(--brand-line); border-radius: 12px; }
</style>
