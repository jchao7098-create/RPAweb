# Intern Learning CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Data Export card that downloads the current Shanghai calendar week's intern RPA learning status as an Excel-compatible CSV.

**Architecture:** A focused learning export service will build a UTF-8 BOM CSV from the frozen weekly roster and latest effective submissions. A new learning-admin route will enforce the admin login surface, while the existing frontend Blob downloader will gain a third card and a Shanghai-week filename.

**Tech Stack:** Flask, SQLAlchemy, Python `csv`, Vue 3, Element Plus, Axios, Vitest, Pytest

## Global Constraints

- Export the current Shanghai natural week, Monday through Sunday.
- Display the week as `YYYY年MM月DD日—YYYY年MM月DD日`.
- Include all rostered interns, including unsubmitted interns.
- Export only the latest currently effective formal submission; do not export draft content.
- Columns are fixed as: 统计周、用户名、邮箱、提交状态、学习内容、学习时长（小时）、完成度（%）、备注、正式提交时间.
- All admin-login-surface accounts may export; user-login-surface accounts may not.
- Use UTF-8 BOM CSV and protect user text beginning with `=`, `+`, `-`, or `@` from spreadsheet formula execution.
- Do not change database tables.
- The workspace is not a Git repository, so no commit step is possible.

---

### Task 1: Build and authorize the recent-week learning CSV

**Files:**
- Create: `backend/app/learning/exports.py`
- Modify: `backend/app/routes/learning.py`
- Test: `backend/tests/test_learning_stats.py`

**Interfaces:**
- Produces: `recent_week_csv(now_utc=None) -> tuple[bytes, date]`.
- Exposes: `GET /learning/admin/export/recent-week`, authenticated by `learning_surface_required('admin')`.

- [x] **Step 1: Write failing service and endpoint tests**

Add imports and tests to `backend/tests/test_learning_stats.py`:

```python
import csv
import io

from app.learning.exports import recent_week_csv


EXPORT_NOW = datetime(2026, 7, 22, 9, tzinfo=timezone.utc)


def test_recent_week_csv_includes_formal_and_unsubmitted_rows(app, roster):
    with app.app_context():
        report = _submitted_report(roster[0], 105, 50)
        submission = db.session.get(WeeklyReportSubmission, report.latest_submission_id)
        submission.content = '=UiPath, advanced'
        submission.remark = '完成\n练习'
        submission.submitted_at = datetime(2026, 7, 22, 3)
        db.session.commit()

        payload, week_start = recent_week_csv(EXPORT_NOW)
        rows = list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))

    assert payload.startswith(b'\xef\xbb\xbf')
    assert week_start == WEEK
    assert rows[0] == ['统计周', '用户名', '邮箱', '提交状态', '学习内容', '学习时长（小时）', '完成度（%）', '备注', '正式提交时间']
    assert len(rows) == 4
    assert rows[1] == [
        '2026年07月20日—2026年07月26日', 'stats-0', 'stats-0@example.com', '已提交',
        "'=UiPath, advanced", '10.5', '50', '完成\n练习', '2026-07-22 11:00',
    ]
    assert rows[2][3:] == ['未提交', '', '', '', '', '']


def test_recent_week_export_requires_admin_login_surface(client, app, roster):
    with app.app_context():
        admin_token = issue_learning_token(roster[0], 'admin')
        user_token = issue_learning_token(roster[0], 'user')

    allowed = client.get('/learning/admin/export/recent-week', headers={
        'Authorization': f'Bearer {admin_token}',
    })
    forbidden = client.get('/learning/admin/export/recent-week', headers={
        'Authorization': f'Bearer {user_token}',
    })

    assert allowed.status_code == 200
    assert allowed.data.startswith(b'\xef\xbb\xbf')
    assert allowed.content_type.startswith('text/csv')
    assert 'intern_rpa_learning_' in allowed.headers['Content-Disposition']
    assert forbidden.status_code == 403
```

- [x] **Step 2: Run the backend tests and verify RED**

Run:

```powershell
cd D:\RPAweb\backend
.\venv\Scripts\python.exe -m pytest tests\test_learning_stats.py -q
```

Expected: collection fails because `app.learning.exports` does not exist.

- [x] **Step 3: Implement the export service**

Create `backend/app/learning/exports.py` with:

```python
import csv
import io
from datetime import datetime, timedelta

from app import db
from app.learning.stats import weekly_stats
from app.learning.time import to_shanghai_iso, week_start_for
from app.models.learning import WeeklyReport, WeeklyReportSubmission


HEADERS = ['统计周', '用户名', '邮箱', '提交状态', '学习内容', '学习时长（小时）', '完成度（%）', '备注', '正式提交时间']
STATUS_LABELS = {
    'missing': '未提交',
    'draft': '未提交',
    'submitted': '已提交',
    'returned': '退回修改中',
    'return_expired': '退回逾期',
}


def _safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def _submission_time(value):
    if value is None:
        return ''
    return datetime.fromisoformat(to_shanghai_iso(value)).strftime('%Y-%m-%d %H:%M')


def recent_week_csv(now_utc=None):
    week_start = week_start_for(now_utc)
    week_end = week_start + timedelta(days=6)
    week_label = f'{week_start:%Y年%m月%d日}—{week_end:%Y年%m月%d日}'
    stats = weekly_stats(week_start, now_utc=now_utc)

    active_report_ids = [row['report_id'] for row in stats['rows'] if row['submitted'] and row['report_id']]
    reports = WeeklyReport.query.filter(WeeklyReport.id.in_(active_report_ids)).all() if active_report_ids else []
    submission_ids = [report.latest_submission_id for report in reports if report.latest_submission_id]
    submissions = WeeklyReportSubmission.query.filter(WeeklyReportSubmission.id.in_(submission_ids)).all() if submission_ids else []
    submissions_by_id = {submission.id: submission for submission in submissions}
    submissions_by_report_id = {
        report.id: submissions_by_id.get(report.latest_submission_id)
        for report in reports
    }

    rows = [HEADERS]
    for row in sorted(stats['rows'], key=lambda item: ((item['username'] or '').lower(), item['user_id'])):
        submission = submissions_by_report_id.get(row['report_id']) if row['submitted'] else None
        rows.append([
            week_label,
            row['username'] or '',
            row['email'] or '',
            STATUS_LABELS.get(row['state'], row['state']),
            submission.content if submission else '',
            submission.hours_tenths / 10 if submission else '',
            submission.completion if submission else '',
            submission.remark if submission else '',
            _submission_time(submission.submitted_at) if submission else '',
        ])

    buffer = io.StringIO(newline='')
    csv.writer(buffer).writerows([[_safe_cell(cell) for cell in row] for row in rows])
    return ('\ufeff' + buffer.getvalue()).encode('utf-8'), week_start
```

- [x] **Step 4: Add the authorized CSV route**

In `backend/app/routes/learning.py`, import `Response` and `recent_week_csv`, then add:

```python
@learning_bp.route('/admin/export/recent-week', methods=['GET'])
@learning_surface_required('admin')
def admin_export_recent_week():
    payload, week_start = recent_week_csv()
    return Response(
        payload,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename=intern_rpa_learning_{week_start:%Y%m%d}.csv',
        },
    )
```

- [x] **Step 5: Run the backend tests and verify GREEN**

Run:

```powershell
cd D:\RPAweb\backend
.\venv\Scripts\python.exe -m pytest tests\test_learning_stats.py -q
```

Expected: 12 tests pass with zero failures.

---

### Task 2: Add the learning export card and Blob download

**Files:**
- Modify: `frontend/src/components/admin/DataExport.vue`
- Create: `frontend/src/components/admin/DataExport.test.js`

**Interfaces:**
- Consumes: `GET /learning/admin/export/recent-week` as a Blob through the shared Axios client.
- Produces: a downloaded filename `实习生RPA学习情况_YYYY-MM-DD.csv`, where the date is the current Shanghai week's Monday.

- [x] **Step 1: Write the failing frontend test**

Create `frontend/src/components/admin/DataExport.test.js`:

```js
// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DataExport from './DataExport.vue'

const http = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/http', () => ({ default: http }))

describe('DataExport learning report', () => {
  let clickAnchor

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-22T04:00:00Z'))
    http.get.mockResolvedValue({ data: new Blob(['csv']) })
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:learning') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    clickAnchor = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('downloads the recent-week learning CSV from the learning admin endpoint', async () => {
    const wrapper = mount(DataExport)
    const button = wrapper.find('[data-test="learning-export"]')
    expect(button.exists()).toBe(true)

    await button.trigger('click')
    await flushPromises()

    expect(http.get).toHaveBeenCalledWith('/learning/admin/export/recent-week', { responseType: 'blob' })
    const clickedAnchor = clickAnchor.mock.contexts[0]
    expect(clickedAnchor.download).toBe('实习生RPA学习情况_2026-07-20.csv')
  })
})
```

- [x] **Step 2: Run the frontend test and verify RED**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/admin/DataExport.test.js
```

Expected: FAIL because the learning export button does not exist.

- [x] **Step 3: Add the Shanghai week helper and export card**

In `DataExport.vue`, add:

```js
const shanghaiWeekStart = () => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  const date = new Date(Date.UTC(Number(values.year), Number(values.month) - 1, Number(values.day)))
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7))
  return date.toISOString().slice(0, 10)
}
```

Append this card inside `.export-cards`:

```vue
<el-card shadow="hover" class="export-card">
  <h3 class="export-card-title">最近一周实习生 RPA 学习情况</h3>
  <p class="export-card-desc">
    导出当前自然周全部实习生的提交状态、学习内容、学习时长、完成度、备注与正式提交时间。
  </p>
  <el-button
    data-test="learning-export"
    type="primary"
    :loading="downloading === 'learning'"
    @click="download('/learning/admin/export/recent-week', `实习生RPA学习情况_${shanghaiWeekStart()}.csv`, 'learning')"
  >
    下载学习情况表
  </el-button>
</el-card>
```

- [x] **Step 4: Run the frontend test and verify GREEN**

Run:

```powershell
cd D:\RPAweb\frontend
npm test -- src/components/admin/DataExport.test.js
```

Expected: 1 test passes with zero failures.

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

Expected: all 23 frontend tests pass, the Vite build exits 0, all 86 backend tests pass, and the site returns HTTP 200.
