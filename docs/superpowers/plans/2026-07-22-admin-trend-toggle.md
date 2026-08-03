# Admin Trend Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the selected intern trend chart when an administrator clicks the same intern row a second time.

**Architecture:** Keep `selected` as the single source of truth for panel visibility. Add an early toggle branch to `loadTrend(row)`: matching `user_id` clears `selected` and `trend` without an API call; a different `user_id` continues through the existing fetch path.

**Tech Stack:** Vue 3 Composition API, Vitest, Vue Test Utils

## Global Constraints

- Do not add a separate close button.
- A second click on the same `user_id` must collapse the panel and must not fetch again.
- Clicking a different `user_id` must continue to select and load that intern.
- Preserve the stopped click behavior of the report-return button.
- Do not modify backend APIs, trend data, or the chart component.
- The workspace is not a Git repository, so no commit step is possible.

---

### Task 1: Toggle the selected intern trend panel

**Files:**
- Modify: `frontend/src/components/admin/LearningStats.vue`
- Test: `frontend/src/components/admin/LearningStats.test.js`

**Interfaces:**
- Consumes: a roster row containing `user_id` and the existing `fetchUserTrend(userId, params)` API.
- Produces: `selected === null` and `trend === []` after a repeated click on the selected row.

- [x] **Step 1: Write the failing repeat-click test**

Replace the existing trend-loading test in `LearningStats.test.js` with:

```js
it('loads a selected user trend and collapses it on a second click', async () => {
  const wrapper = mount(LearningStats)
  await flushPromises()
  const row = wrapper.find('[data-test="roster-row"]')

  await row.trigger('click')
  await flushPromises()
  expect(api.fetchUserTrend).toHaveBeenCalledWith(8, expect.any(Object))
  expect(wrapper.text()).toContain('intern 的趋势')

  await row.trigger('click')
  await flushPromises()
  expect(wrapper.text()).not.toContain('intern 的趋势')
  expect(api.fetchUserTrend).toHaveBeenCalledTimes(1)
})
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/admin/LearningStats.test.js
```

Expected: FAIL because the second click leaves `selected` set and calls `fetchUserTrend` a second time.

- [x] **Step 3: Implement the same-row toggle branch**

Replace `loadTrend` in `LearningStats.vue` with:

```js
async function loadTrend(row) {
  if (selected.value?.user_id === row.user_id) {
    selected.value = null
    trend.value = []
    return
  }
  selected.value = row
  const value = await fetchUserTrend(row.user_id, { from_week: undefined, to_week: weekStart.value || undefined })
  trend.value = value?.points || value?.items || []
}
```

- [x] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/admin/LearningStats.test.js
```

Expected: all 4 tests pass with zero failures.

- [x] **Step 5: Run complete verification**

Run:

```powershell
cd D:\RPAweb\frontend
npm test
npm run build
cd D:\RPAweb\backend
.\venv\Scripts\python.exe -m pytest -q
(Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173').StatusCode
```

Expected: all 22 frontend tests pass, the Vite build exits 0, all 84 backend tests pass, and the site returns HTTP 200.
