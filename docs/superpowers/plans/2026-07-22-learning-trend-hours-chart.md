# Learning Trend Hours Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each learning-hours bar use a fixed 40-hour weekly scale and show its real hour value directly above the bar.

**Architecture:** Keep the existing SVG chart and backend trend response unchanged. Replace the data-relative hours maximum with a constant 40-hour scale, cap only the rendered height for values above 40, and add one SVG text label per non-null hours value while preserving the independent completion percentage line.

**Tech Stack:** Vue 3 Composition API, SVG, Vitest, Vue Test Utils

## Global Constraints

- Forty hours is the fixed full-height baseline.
- Values above 40 hours keep their real label but do not overflow the plot area.
- Remove the standalone hours axis title.
- Preserve week labels, completion points and line, null-hours behavior, and the empty state.
- Do not change backend APIs or database models.
- The workspace is not a Git repository, so no commit step is possible.

---

### Task 1: Fixed-scale hour bars with direct labels

**Files:**
- Modify: `frontend/src/components/charts/LearningTrendChart.vue`
- Test: `frontend/src/components/charts/LearningTrendChart.test.js`

**Interfaces:**
- Consumes: `points: Array<{ week_start: string, hours: number | null, completion: number | null }>`
- Produces: SVG elements tagged `data-test="hours-bar"` and `data-test="hours-label"`; bar height uses a 40-hour denominator.

- [x] **Step 1: Write the failing fixed-scale and label test**

Add this test to `LearningTrendChart.test.js`:

```js
it('uses a fixed 40-hour scale and labels each submitted hour value', () => {
  const wrapper = mount(LearningTrendChart, { props: { points: [
    { week_start: '2026-07-13', hours: 4, completion: 50 },
    { week_start: '2026-07-20', hours: 8, completion: 80 },
  ] } })

  const bars = wrapper.findAll('[data-test="hours-bar"]')
  expect(Number(bars[0].attributes('height'))).toBeCloseTo(20)
  expect(Number(bars[1].attributes('height'))).toBeCloseTo(40)
  expect(wrapper.findAll('[data-test="hours-label"]').map((label) => label.text())).toEqual(['4 小时', '8 小时'])
  expect(wrapper.findAll('text').some((node) => node.text() === '小时')).toBe(false)
})
```

Extend the existing submitted-hours test with:

```js
expect(wrapper.findAll('[data-test="hours-label"]')).toHaveLength(2)
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/charts/LearningTrendChart.test.js
```

Expected: FAIL because the old data-relative maximum renders 4 and 8 hours as 100px and 200px instead of 20px and 40px, and no `hours-label` elements exist.

- [x] **Step 3: Implement the fixed 40-hour rendering rule**

In `LearningTrendChart.vue`, replace the computed maximum and current hours mapping with:

```js
const hourScaleMax = 40
const clampedHours = (hours) => Math.min(hourScaleMax, Math.max(0, Number(hours) || 0))
const hourY = (hours) => padding.top + usableHeight - clampedHours(hours) / hourScaleMax * usableHeight
const hourLabel = (hours) => `${Number(hours)} 小时`
const hourLabelY = (hours) => Math.max(14, hourY(hours) - 6)
```

For every `point.hours != null`, retain the existing rectangle and add:

```vue
<text
  data-test="hours-label"
  :x="x(index)"
  :y="hourLabelY(point.hours)"
  text-anchor="middle"
  class="hours-value"
>{{ hourLabel(point.hours) }}</text>
```

Remove the standalone SVG text node containing `小时`, retain the `100%` label, and add:

```css
.hours-value { fill: #5d3ee8; font-size: 10px; font-weight: 700; }
```

- [x] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/charts/LearningTrendChart.test.js
```

Expected: 3 tests pass with zero failures.

- [x] **Step 5: Run full regression verification**

Run:

```powershell
cd D:\RPAweb\frontend
npm test
npm run build
cd D:\RPAweb\backend
.\venv\Scripts\python.exe -m pytest -q
```

Expected: all frontend tests pass, Vite production build exits 0, and all 84 backend tests pass.

- [x] **Step 6: Verify the local site remains available**

Run:

```powershell
(Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173').StatusCode
```

Expected: `200`.
