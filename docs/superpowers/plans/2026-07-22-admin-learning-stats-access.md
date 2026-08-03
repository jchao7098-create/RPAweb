# Admin Learning Stats Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow every account authenticated through `/admin/login` to view all intern learning statistics while keeping report returns and role administration restricted to HR and boss roles.

**Architecture:** Add a signed `login_surface` claim to the existing learning token and derive separate read and manage capability flags from that claim plus the current SQLite learning role. Apply surface authorization on the backend, then make the admin navigation, router guard, and return action consume the server-provided capabilities.

**Tech Stack:** Flask, itsdangerous, Flask-SQLAlchemy, pytest, Vue 3 Composition API, Vue Router, Vitest, Vue Test Utils, Vite.

## Global Constraints

- Do not modify the shared MySQL schema or data; learning data remains in `backend/var/assets.db`.
- An account is considered an administrator only because it authenticated through `/admin/login`, as explicitly confirmed for this project.
- All administrator-entry sessions may read weekly statistics and user trends.
- Only administrator-entry sessions whose current learning role is `hr` or `boss` may return reports, change roles, or read role audit logs.
- User-entry sessions may not read aggregate learning statistics; administrator-entry sessions may not use intern report endpoints.
- Old learning tokens without `login_surface` must fail with `401` and require a fresh login.
- The repository has no Git metadata, so commit steps are intentionally omitted; do not initialize Git as part of this change.

---

### Task 1: Encode and Validate the Login Surface

**Files:**
- Modify: `backend/app/learning/auth.py`
- Modify: `backend/app/routes/user.py`
- Modify: `backend/app/routes/admin.py`
- Modify: `backend/tests/test_learning_auth.py`

**Interfaces:**
- Produces: `issue_learning_token(user_id: int, login_surface: str) -> str`
- Produces: `decode_learning_token(token: str) -> tuple[int, str]`
- Produces: `learning_login_fields(user_id: int, login_surface: str) -> dict`
- Produces: request globals `g.learning_user_id: int` and `g.learning_login_surface: str`
- Produces: `learning_surface_required(*login_surfaces: str)` decorator
- Preserves: `learning_roles_required(*roles: str, login_surface: str | None = None)` decorator

- [ ] **Step 1: Add failing login-surface and legacy-token tests**

Add explicit surface assertions to `backend/tests/test_learning_auth.py` and create a legacy token manually:

```python
def test_user_and_admin_login_tokens_preserve_the_login_surface(client, app):
    with app.app_context():
        db.session.add(User(
            username='surface-user',
            email='surface@example.com',
            password='secret1',
            created_at=utc_now(),
        ))
        db.session.commit()

    user_response = client.post('/user/login', json={
        'username': 'surface-user', 'password': 'secret1',
    })
    admin_response = client.post('/admin/login', json={
        'username': 'surface-user', 'password': 'secret1',
    })

    with app.app_context():
        assert decode_learning_token(user_response.json['learning_token']) == (
            user_response.json['user_id'], 'user',
        )
        assert decode_learning_token(admin_response.json['learning_token']) == (
            admin_response.json['admin_id'], 'admin',
        )


def test_legacy_token_without_login_surface_is_rejected(client, app):
    with app.app_context():
        legacy = URLSafeTimedSerializer(
            app.config['LEARNING_TOKEN_SECRET'], salt='rpa-learning-v1'
        ).dumps({'user_id': 17, 'purpose': 'learning'})

    response = client.get('/learning/me', headers={
        'Authorization': f'Bearer {legacy}',
    })

    assert response.status_code == 401
    assert response.json == {'error': 'Invalid learning token'}
```

Update every direct test call from `issue_learning_token(user_id)` to an explicit `issue_learning_token(user_id, 'user')` or `issue_learning_token(user_id, 'admin')` according to the endpoint under test.

- [ ] **Step 2: Run the focused authentication tests and confirm failure**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests\test_learning_auth.py -q
```

Expected: failures because `issue_learning_token`, `decode_learning_token`, and `learning_login_fields` do not yet preserve `login_surface`.

- [ ] **Step 3: Implement strict signed-surface tokens and decorators**

In `backend/app/learning/auth.py`, validate a closed set of surfaces and populate both request globals:

```python
_LOGIN_SURFACES = ('user', 'admin')


def _validate_login_surface(login_surface):
    if login_surface not in _LOGIN_SURFACES:
        raise LearningUnauthorizedError('Invalid learning token')
    return login_surface


def issue_learning_token(user_id, login_surface):
    return _serializer().dumps({
        'user_id': int(user_id),
        'purpose': _TOKEN_PURPOSE,
        'login_surface': _validate_login_surface(login_surface),
    })


def decode_learning_token(token):
    if not token:
        raise LearningUnauthorizedError('Missing learning token')
    try:
        payload = _serializer().loads(
            token,
            max_age=current_app.config['LEARNING_TOKEN_MAX_AGE_SECONDS'],
        )
    except (BadSignature, SignatureExpired):
        raise LearningUnauthorizedError('Invalid or expired learning token')
    if not isinstance(payload, dict) or payload.get('purpose') != _TOKEN_PURPOSE:
        raise LearningUnauthorizedError('Invalid learning token')
    try:
        user_id = int(payload['user_id'])
    except (KeyError, TypeError, ValueError):
        raise LearningUnauthorizedError('Invalid learning token')
    if isinstance(payload['user_id'], bool):
        raise LearningUnauthorizedError('Invalid learning token')
    return user_id, _validate_login_surface(payload.get('login_surface'))


def learning_auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        scheme, _, token = request.headers.get('Authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not token:
            raise LearningUnauthorizedError('Missing learning token')
        g.learning_user_id, g.learning_login_surface = decode_learning_token(token)
        return view(*args, **kwargs)
    return wrapped


def learning_surface_required(*login_surfaces):
    invalid = set(login_surfaces) - set(_LOGIN_SURFACES)
    if invalid:
        raise ValueError('Unknown learning login surface')

    def decorator(view):
        @learning_auth_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.learning_login_surface not in login_surfaces:
                raise LearningForbiddenError('Learning login surface is not permitted')
            return view(*args, **kwargs)
        return wrapped
    return decorator


def learning_roles_required(*roles, login_surface=None):
    def decorator(view):
        @learning_auth_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            from app.learning.roles import get_role
            if login_surface is not None and g.learning_login_surface != login_surface:
                raise LearningForbiddenError('Learning login surface is not permitted')
            if get_role(g.learning_user_id) not in roles:
                raise LearningForbiddenError('Learning role is not permitted')
            return view(*args, **kwargs)
        return wrapped
    return decorator


def learning_login_fields(user_id, login_surface):
    from app.learning.roles import get_role
    return {
        'learning_token': issue_learning_token(user_id, login_surface),
        'learning_role': get_role(user_id),
    }
```

Call `learning_login_fields(user.id, 'user')` in `backend/app/routes/user.py` and `learning_login_fields(user.id, 'admin')` in `backend/app/routes/admin.py`.

- [ ] **Step 4: Run authentication tests and confirm success**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests\test_learning_auth.py -q
```

Expected: all authentication tests pass, including legacy-token rejection.

---

### Task 2: Split Read and Manage Authorization on Learning APIs

**Files:**
- Modify: `backend/app/learning/roles.py`
- Modify: `backend/app/routes/learning.py`
- Modify: `backend/tests/test_learning_roles.py`
- Modify: `backend/tests/test_learning_reports.py`
- Modify: `backend/tests/test_learning_stats.py`

**Interfaces:**
- Consumes: `g.learning_login_surface` and `learning_surface_required` from Task 1
- Produces: `get_identity(user_id: int, login_surface: str) -> dict`
- Produces: `can_view_learning_stats: bool` in `GET /learning/me`
- Refines: `can_manage_learning: bool` to require admin surface plus HR/boss role

- [ ] **Step 1: Add failing API authorization tests**

Add tests proving an employee-role admin can read but cannot manage, and a user token cannot read aggregate data:

```python
def test_employee_role_admin_can_read_weekly_stats(client, app, roster):
    with app.app_context():
        token = issue_learning_token(roster[0], 'admin')
    response = client.get(
        '/learning/admin/weekly-stats?week_start=2026-07-20',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == 200
    assert response.json['week_start'] == '2026-07-20'


def test_user_surface_cannot_read_weekly_stats(client, app, roster):
    with app.app_context():
        token = issue_learning_token(roster[0], 'user')
    response = client.get(
        '/learning/admin/weekly-stats?week_start=2026-07-20',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert response.status_code == 403
    assert response.json == {'error': 'Learning login surface is not permitted'}


def test_employee_role_admin_cannot_open_role_management(client, employee_headers):
    response = client.get('/learning/admin/users', headers=employee_headers)
    assert response.status_code == 403


def test_identity_separates_stats_read_from_management(app, users):
    with app.app_context():
        identity = get_identity(users['employee'], 'admin')
    assert identity['can_view_learning_stats'] is True
    assert identity['can_manage_learning'] is False
    assert identity['can_view_learning_report'] is False
```

Set `hr_headers` and `employee_headers` in `backend/tests/test_learning_roles.py` to issue `'admin'` tokens. Set report-test tokens to `'user'`.

- [ ] **Step 2: Run focused role, report, and stats tests and confirm failure**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests\test_learning_roles.py backend\tests\test_learning_reports.py backend\tests\test_learning_stats.py -q
```

Expected: failures because identity has no stats-read capability and stats still require HR/boss.

- [ ] **Step 3: Derive capabilities from surface and role**

Change `get_identity` in `backend/app/learning/roles.py` to accept the authenticated surface:

```python
def get_identity(user_id, login_surface):
    week_start = _week_start()
    ensure_roster_week(week_start)
    role = get_role(user_id)
    roster_member = is_roster_member(user_id, week_start)
    is_user_surface = login_surface == 'user'
    is_admin_surface = login_surface == 'admin'
    return {
        'user_id': int(user_id),
        'role': role,
        'login_surface': login_surface,
        'week_start': week_start.isoformat(),
        'week_end': (week_start + timedelta(days=6)).isoformat(),
        'is_current_roster_member': roster_member,
        'can_view_learning_report': is_user_surface and (role == 'intern' or roster_member),
        'can_submit_current_week': is_user_surface and roster_member,
        'can_view_learning_stats': is_admin_surface,
        'can_manage_learning': is_admin_surface and role in ('hr', 'boss'),
    }
```

Pass `g.learning_login_surface` from the `/learning/me` route.

- [ ] **Step 4: Apply surface checks to every learning route**

In `backend/app/routes/learning.py`:

```python
from app.learning.auth import (
    learning_auth_required,
    learning_roles_required,
    learning_surface_required,
)

@learning_bp.route('/me', methods=['GET'])
@learning_auth_required
def me():
    return jsonify(get_identity(g.learning_user_id, g.learning_login_surface))
```

Replace authentication on all report read/write/history/detail endpoints with:

```python
@learning_surface_required('user')
```

Protect the two read-only statistics endpoints with:

```python
@learning_surface_required('admin')
```

Protect report return, user list, role change, and role audit endpoints with:

```python
@learning_roles_required('hr', 'boss', login_surface='admin')
```

- [ ] **Step 5: Run the backend learning test suite**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: all backend tests pass with no MySQL schema mutation.

---

### Task 3: Expose Separate Read and Manage Capabilities in Navigation

**Files:**
- Modify: `frontend/src/utils/learningSession.js`
- Modify: `frontend/src/utils/learningSession.test.js`
- Modify: `frontend/src/views/AdminView.vue`
- Create: `frontend/src/views/AdminView.test.js`
- Modify: `frontend/src/router/index.js`

**Interfaces:**
- Consumes: `can_view_learning_stats` and `can_manage_learning` from `/learning/me`
- Produces: `canViewLearningStats(profile: object) -> boolean`
- Preserves: `canManageLearning(profile: object) -> boolean`
- Produces router audiences: `stats`, `manage`, and `report`

- [ ] **Step 1: Add failing capability and admin-navigation tests**

Extend `frontend/src/utils/learningSession.test.js`:

```javascript
import {
  canManageLearning,
  canViewLearningStats,
  canViewReport,
  clearLearningSession,
  getLearningToken,
  setLearningSession,
} from './learningSession'

it('separates statistics viewing from learning management', () => {
  expect(canViewLearningStats({ can_view_learning_stats: true })).toBe(true)
  expect(canViewLearningStats({ can_manage_learning: true })).toBe(false)
  expect(canManageLearning({ can_view_learning_stats: true })).toBe(false)
})
```

Create `frontend/src/views/AdminView.test.js` with a small `ConsoleShell` stub that renders section labels:

```javascript
// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminView from './AdminView.vue'

const api = vi.hoisted(() => ({ loadLearningProfile: vi.fn() }))
vi.mock('@/api/learning', () => api)

const ConsoleShell = {
  props: ['sections'],
  template: '<div><span v-for="section in sections" :key="section.path">{{ section.label }}</span></div>',
}

describe('AdminView learning navigation', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows stats but not role management to a read-only admin', async () => {
    api.loadLearningProfile.mockResolvedValue({
      can_view_learning_stats: true,
      can_manage_learning: false,
    })
    const wrapper = mount(AdminView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()
    expect(wrapper.text()).toContain('学习统计')
    expect(wrapper.text()).not.toContain('人员权限')
  })

  it('shows both entries to an HR or boss admin', async () => {
    api.loadLearningProfile.mockResolvedValue({
      can_view_learning_stats: true,
      can_manage_learning: true,
    })
    const wrapper = mount(AdminView, { global: { stubs: { ConsoleShell } } })
    await flushPromises()
    expect(wrapper.text()).toContain('学习统计')
    expect(wrapper.text()).toContain('人员权限')
  })
})
```

- [ ] **Step 2: Run focused frontend tests and confirm failure**

Run:

```powershell
npm test -- --run src/utils/learningSession.test.js src/views/AdminView.test.js
```

Working directory: `frontend`

Expected: failures because `canViewLearningStats` and split navigation do not exist.

- [ ] **Step 3: Implement split capability helpers and menu construction**

Add to `frontend/src/utils/learningSession.js`:

```javascript
export const canViewLearningStats = (profile) => profile?.can_view_learning_stats === true
```

In `frontend/src/views/AdminView.vue`, import both helpers and build sections independently:

```javascript
import { canManageLearning, canViewLearningStats } from '@/utils/learningSession'

const visibleSections = computed(() => {
  const result = [...sections]
  if (canViewLearningStats(learningProfile.value)) {
    result.push({
      path: '/admin/LearningStats',
      label: '学习统计',
      desc: '查看实习生周报提交、学习时长与个人趋势',
    })
  }
  if (canManageLearning(learningProfile.value)) {
    result.push({
      path: '/admin/RoleManagement',
      label: '人员权限',
      desc: '调整学习模块角色并查看角色审计记录',
    })
  }
  return result
})
```

- [ ] **Step 4: Split router guards for stats and management**

In `frontend/src/router/index.js`, import `canViewLearningStats`, set `LearningStats` metadata to `stats`, set `RoleManagement` metadata to `manage`, and calculate permissions explicitly:

```javascript
const capabilityChecks = {
  stats: canViewLearningStats,
  manage: canManageLearning,
  report: canViewReport,
}

router.beforeEach(async (to) => {
  const audience = to.meta.learningAudience
  if (!audience) return true
  const isAdminRoute = audience === 'stats' || audience === 'manage'
  const loginPath = isAdminRoute ? '/adminLogin' : '/login'
  const rootPath = isAdminRoute ? '/admin' : '/main'
  if (!getLearningToken()) return loginPath
  try {
    const profile = await loadLearningProfile({ force: true })
    return capabilityChecks[audience]?.(profile) ? true : rootPath
  } catch {
    return getLearningToken() ? rootPath : loginPath
  }
})
```

- [ ] **Step 5: Run navigation and session tests**

Run:

```powershell
npm test -- --run src/utils/learningSession.test.js src/views/AdminView.test.js
```

Working directory: `frontend`

Expected: all focused tests pass.

---

### Task 4: Make the Statistics Page Read-Only for Ordinary Admins

**Files:**
- Modify: `frontend/src/components/admin/LearningStats.vue`
- Modify: `frontend/src/components/admin/LearningStats.test.js`

**Interfaces:**
- Consumes: `loadLearningProfile() -> Promise<object>`
- Consumes: `canManageLearning(profile) -> boolean`
- Preserves: all existing statistics and trend requests for read-only admins
- Restricts: report-return UI to `can_manage_learning === true`

- [ ] **Step 1: Add failing ordinary-admin and HR/boss UI tests**

Expand the hoisted API mock and add two tests in `LearningStats.test.js`:

```javascript
const api = vi.hoisted(() => ({
  fetchWeeklyStats: vi.fn(),
  fetchUserTrend: vi.fn(),
  loadLearningProfile: vi.fn(),
  returnLearningReport: vi.fn(),
}))

it('hides report return from a read-only administrator', async () => {
  api.loadLearningProfile.mockResolvedValue({ can_manage_learning: false })
  const wrapper = mount(LearningStats)
  await flushPromises()
  expect(wrapper.find('[data-test="return-report"]').exists()).toBe(false)
})

it('shows report return to an HR or boss administrator', async () => {
  api.loadLearningProfile.mockResolvedValue({ can_manage_learning: true })
  const wrapper = mount(LearningStats)
  await flushPromises()
  expect(wrapper.find('[data-test="return-report"]').exists()).toBe(true)
})
```

Set `api.loadLearningProfile.mockResolvedValue({ can_manage_learning: true })` in the existing validation test so it can still open the return dialog.

- [ ] **Step 2: Run the component test and confirm failure**

Run:

```powershell
npm test -- --run src/components/admin/LearningStats.test.js
```

Working directory: `frontend`

Expected: the read-only test fails because the current button trusts `row.can_return`.

- [ ] **Step 3: Gate return actions with the authoritative profile**

Update `LearningStats.vue`:

```javascript
import { fetchUserTrend, fetchWeeklyStats, loadLearningProfile, returnLearningReport } from '@/api/learning'
import { canManageLearning } from '@/utils/learningSession'

const learningProfile = ref(null)
const canReturnReports = computed(() => canManageLearning(learningProfile.value))

onMounted(async () => {
  weekStart.value = monday()
  try {
    const [profile] = await Promise.all([
      loadLearningProfile(),
      loadStats(),
    ])
    learningProfile.value = profile
  } catch (value) {
    error.value = value?.response?.data?.error || '统计加载失败'
  }
})
```

Replace the button condition with an explicit capability and valid submitted report check:

```vue
<button
  v-if="canReturnReports && row.report_id && row.state === 'submitted'"
  data-test="return-report"
  class="btn btn-gray"
  @click.stop="openReturn(row)"
>
  退回修改
</button>
```

- [ ] **Step 4: Run the statistics component tests**

Run:

```powershell
npm test -- --run src/components/admin/LearningStats.test.js
```

Working directory: `frontend`

Expected: all LearningStats tests pass for read-only and managing administrators.

---

### Task 5: Update Project Rules and Perform Full Verification

**Files:**
- Modify: `CLAUDE.md`
- Reference: `docs/superpowers/specs/2026-07-22-admin-learning-stats-access-design.md`

**Interfaces:**
- Documents: administrator-entry read capability versus HR/boss manage capability
- Verifies: backend tests, frontend tests, and production build

- [ ] **Step 1: Update the learning-module convention**

Replace the stale HR/boss-only navigation sentence in `CLAUDE.md` with:

```markdown
- 学习令牌必须记录登录入口：`/user/login` 签发 `user`，`/admin/login` 签发 `admin`；旧格式令牌拒绝并要求重新登录。所有 `admin` 入口会话可查看学习统计与个人趋势，只有同时具备 `hr`/`boss` 角色的 `admin` 会话可退回周报、调整角色和查看角色审计；用户端周报接口仅接受 `user` 入口会话。
```

- [ ] **Step 2: Run the full backend test suite**

Run:

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 3: Run the full frontend test suite**

Run:

```powershell
npm test
```

Working directory: `frontend`

Expected: all Vitest suites pass with zero failures.

- [ ] **Step 4: Build the frontend for production**

Run:

```powershell
npm run build
```

Working directory: `frontend`

Expected: Vite exits with code `0` and writes production assets under `frontend/dist`.

- [ ] **Step 5: Verify exact route behavior with Flask test-client requests**

Use the automated tests as the executable route probe and confirm these response classes in their output:

```text
admin-surface employee -> GET weekly-stats: 200
user-surface intern -> GET weekly-stats: 403
admin-surface employee -> GET admin/users: 403
admin-surface hr/boss -> GET admin/users: 200
legacy no-surface token -> GET learning/me: 401
```

Do not perform schema writes against the configured production MySQL instance during verification.
