# User First-Login Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a required user-login position choice that is persisted once, immediately enrolls first-time interns in the current roster, and makes the RPA learning record available in the user workspace.

**Architecture:** Reuse the existing SQLite `user_roles`, role audit, and weekly roster tables. A focused role service will atomically confirm the first employment type; `/user/login` will call it only after credentials pass, while Vue renders and submits the position only for the user audience.

**Tech Stack:** Flask, Flask-SQLAlchemy, SQLite, pytest, Vue 3 Composition API, Vitest, Vue Test Utils, Vite.

## Global Constraints

- `employment_type` accepts only `intern` and `employee`.
- The first selection creates an explicit `UserRole`, including an explicit `employee` mapping.
- A first-time intern joins the current `WeeklyRoster` immediately, even when the week snapshot already exists.
- Existing role mappings are never overwritten by user login; `intern` maps to intern and `employee/hr/boss` map to formal employee.
- A later mismatched selection returns `409`; invalid or missing position after valid credentials returns `422`.
- Invalid credentials remain `401` regardless of submitted position, so role state is not leaked.
- Administrator login does not require or persist `employment_type`.
- HR/boss role management remains the only later mutation path.
- MySQL `users` remains read-only; all new writes go to `assets.db`.
- The repository has no Git metadata, so commit steps are intentionally omitted.

---

### Task 1: Persist the First Position and Immediate Intern Roster Membership

**Files:**
- Modify: `backend/app/learning/roles.py`
- Modify: `backend/tests/test_learning_roles.py`

**Interfaces:**
- Produces: `employment_type_for_role(role: str) -> str`
- Produces: `confirm_initial_employment_type(user_id: int, employment_type: str, week_start: date | None = None) -> str`
- Raises: `LearningValidationError` for invalid input and `LearningConflictError` for a fixed-position mismatch

- [ ] **Step 1: Write failing service tests**

Add tests that prove explicit employee persistence, immediate intern enrollment, idempotence, and mismatch rejection:

```python
def test_first_employee_selection_creates_explicit_mapping_and_audit(app, users):
    with app.app_context():
        result = confirm_initial_employment_type(users['employee'], 'employee', WEEK_START)
        assert result == 'employee'
        assert db.session.get(UserRole, users['employee']).role == 'employee'
        audit = RoleChangeLog.query.filter_by(target_user_id=users['employee']).one()
        assert audit.source == 'self_selection'
        assert audit.operator_user_id == users['employee']


def test_first_intern_selection_joins_frozen_current_week_immediately(app, users):
    with app.app_context():
        ensure_roster_week(WEEK_START)
        result = confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert result == 'intern'
        assert is_roster_member(users['target'], WEEK_START) is True


def test_same_initial_selection_is_idempotent(app, users):
    with app.app_context():
        confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert RoleChangeLog.query.filter_by(target_user_id=users['target']).count() == 1
        assert WeeklyRoster.query.filter_by(
            week_start=WEEK_START, user_id=users['target']
        ).count() == 1


def test_fixed_position_rejects_a_different_login_selection(app, users):
    with app.app_context():
        confirm_initial_employment_type(users['target'], 'employee', WEEK_START)
        with pytest.raises(LearningConflictError, match='fixed'):
            confirm_initial_employment_type(users['target'], 'intern', WEEK_START)
        assert db.session.get(UserRole, users['target']).role == 'employee'


@pytest.mark.parametrize('value', [None, '', 'boss', 7])
def test_initial_position_rejects_invalid_values(app, users, value):
    with app.app_context(), pytest.raises(LearningValidationError):
        confirm_initial_employment_type(users['target'], value, WEEK_START)
```

- [ ] **Step 2: Run the role tests and verify RED**

Run from `backend`:

```powershell
venv\Scripts\python.exe -m pytest tests\test_learning_roles.py -q
```

Expected: import or name failures because `confirm_initial_employment_type` does not exist.

- [ ] **Step 3: Implement the atomic first-selection service**

In `backend/app/learning/roles.py`, import `LearningConflictError` and add:

```python
EMPLOYMENT_TYPES = ('employee', 'intern')


def employment_type_for_role(role):
    return 'intern' if role == 'intern' else 'employee'


def _validate_employment_type(employment_type):
    if not isinstance(employment_type, str) or employment_type not in EMPLOYMENT_TYPES:
        raise LearningValidationError('employment_type must be employee or intern')
    return employment_type


def _existing_employment_type(user_id, requested):
    role_row = db.session.get(UserRole, int(user_id))
    if role_row is None:
        return None
    fixed = employment_type_for_role(role_row.role)
    if fixed != requested:
        raise LearningConflictError('Employment type is fixed; contact an administrator to change it')
    return fixed


def confirm_initial_employment_type(user_id, employment_type, week_start=None):
    requested = _validate_employment_type(employment_type)
    user_id = int(user_id)
    fixed = _existing_employment_type(user_id, requested)
    if fixed is not None:
        return fixed

    roster_week = _week_start(week_start)
    ensure_roster_week(roster_week)
    db.session.add(UserRole(
        user_id=user_id,
        role=requested,
        assigned_by_user_id=user_id,
    ))
    db.session.add(RoleChangeLog(
        target_user_id=user_id,
        old_role='employee',
        new_role=requested,
        operator_user_id=user_id,
        source='self_selection',
    ))
    if requested == 'intern':
        db.session.add(WeeklyRoster(week_start=roster_week, user_id=user_id))
    try:
        db.session.commit()
        return requested
    except IntegrityError:
        db.session.rollback()
        fixed = _existing_employment_type(user_id, requested)
        if fixed is not None:
            return fixed
        raise
    except Exception:
        db.session.rollback()
        raise
```

- [ ] **Step 4: Run role tests and verify GREEN**

Run:

```powershell
venv\Scripts\python.exe -m pytest tests\test_learning_roles.py -q
```

Expected: all role tests pass.

---

### Task 2: Integrate Position Confirmation into User Login

**Files:**
- Modify: `backend/app/routes/user.py`
- Modify: `backend/tests/test_learning_auth.py`

**Interfaces:**
- Consumes: `confirm_initial_employment_type(user_id, employment_type) -> str`
- Produces: required `/user/login` request field `employment_type`
- Produces: successful response field `employment_type`
- Preserves: `/admin/login` request and response behavior

- [ ] **Step 1: Write failing login integration tests**

Update successful user-login tests to send `employment_type`, then add:

```python
@pytest.mark.parametrize('value', [None, '', 'boss'])
def test_user_login_requires_a_valid_employment_type_after_credentials_pass(client, app, value):
    with app.app_context():
        db.session.add(User(
            username='position-required', email='position-required@example.com',
            password='secret1', created_at=utc_now(),
        ))
        db.session.commit()
    payload = {'username': 'position-required', 'password': 'secret1'}
    if value is not None:
        payload['employment_type'] = value
    response = client.post('/user/login', json=payload)
    assert response.status_code == 422


def test_first_intern_login_can_submit_in_the_current_week(client, app):
    with app.app_context():
        db.session.add(User(
            username='first-intern', email='first-intern@example.com',
            password='secret1', created_at=utc_now(),
        ))
        db.session.commit()
    login = client.post('/user/login', json={
        'username': 'first-intern', 'password': 'secret1',
        'employment_type': 'intern',
    })
    profile = client.get('/learning/me', headers={
        'Authorization': f"Bearer {login.json['learning_token']}",
    })
    assert login.status_code == 200
    assert login.json['employment_type'] == 'intern'
    assert profile.json['can_view_learning_report'] is True
    assert profile.json['can_submit_current_week'] is True


def test_fixed_position_mismatch_returns_409_without_changing_role(client, app):
    with app.app_context():
        user = User(
            username='fixed-worker', email='fixed-worker@example.com',
            password='secret1', created_at=utc_now(),
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(UserRole(user_id=user.id, role='employee'))
        db.session.commit()
    response = client.post('/user/login', json={
        'username': 'fixed-worker', 'password': 'secret1',
        'employment_type': 'intern',
    })
    assert response.status_code == 409
    assert '职位已固定' in response.json['message']


def test_invalid_credentials_still_return_401_before_position_validation(client):
    response = client.post('/user/login', json={
        'username': 'absent', 'password': 'secret1',
    })
    assert response.status_code == 401
    assert response.json == {'message': '账号或密码错误'}
```

- [ ] **Step 2: Run authentication tests and verify RED**

Run from `backend`:

```powershell
venv\Scripts\python.exe -m pytest tests\test_learning_auth.py -q
```

Expected: the new position validation, response field, and current-week capability assertions fail.

- [ ] **Step 3: Call the service after credential verification**

In `backend/app/routes/user.py`, normalize JSON and catch learning-domain errors locally because this route is outside the learning blueprint:

```python
from app.learning.errors import LearningError
from app.learning.roles import confirm_initial_employment_type

data = request.get_json(silent=True) or {}
# existing account/password lookup remains unchanged
if not user or user.password != password:
    return jsonify({'message': '账号或密码错误'}), 401

try:
    employment_type = confirm_initial_employment_type(
        user.id, data.get('employment_type')
    )
except LearningError as error:
    message = error.message
    if error.status_code == 409:
        message = '职位已固定，如需修改请联系管理员'
    return jsonify({'message': message}), error.status_code

payload = {
    'message': '登录成功',
    'user_id': user.id,
    'employment_type': employment_type,
}
payload.update(learning_login_fields(user.id, 'user'))
return jsonify(payload), 200
```

- [ ] **Step 4: Run authentication and role tests**

Run:

```powershell
venv\Scripts\python.exe -m pytest tests\test_learning_auth.py tests\test_learning_roles.py -q
```

Expected: all focused backend tests pass.

---

### Task 3: Add the Position Selector to User Login Only

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/LoginView.test.js`

**Interfaces:**
- Produces: `employment_type` in user-login JSON only
- Preserves: admin-login JSON without `employment_type`
- Uses values: `intern` and `employee`

- [ ] **Step 1: Write failing LoginView tests**

Create `frontend/src/views/LoginView.test.js` with mocked HTTP, router, and credential storage:

```javascript
// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginView from './LoginView.vue'

const http = vi.hoisted(() => ({ post: vi.fn() }))
const router = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('@/api/http', () => ({ default: http }))
vi.mock('@/router', () => ({ default: router }))
vi.mock('@/utils/credentialStore', () => ({
  getSavedPassword: vi.fn(() => ''), saveAccount: vi.fn(), removeAccount: vi.fn(),
}))

describe('LoginView position selection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.ElMessage = { error: vi.fn(), success: vi.fn() }
    http.post.mockResolvedValue({ data: {
      message: '登录成功', user_id: 1, learning_token: 'signed', learning_role: 'intern',
    } })
  })

  it('shows and submits position for user login', async () => {
    const wrapper = mount(LoginView, {
      props: { audience: 'user' }, global: { stubs: { RouterLink: true } },
    })
    await wrapper.get('input[type="text"]').setValue('worker')
    await wrapper.get('input[type="password"]').setValue('secret1')
    await wrapper.get('[data-test="employment-type"]').setValue('intern')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/user/login', {
      username: 'worker', password: 'secret1', employment_type: 'intern',
    })
  })

  it('does not render or send position for admin login', async () => {
    http.post.mockResolvedValue({ data: {
      message: '登录成功', admin_id: 1, learning_token: 'signed', learning_role: 'employee',
    } })
    const wrapper = mount(LoginView, {
      props: { audience: 'admin' }, global: { stubs: { RouterLink: true } },
    })
    expect(wrapper.find('[data-test="employment-type"]').exists()).toBe(false)
    await wrapper.get('input[type="text"]').setValue('admin')
    await wrapper.get('input[type="password"]').setValue('secret1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/admin/login', {
      username: 'admin', password: 'secret1',
    })
  })
})
```

- [ ] **Step 2: Run the LoginView test and verify RED**

Run from `frontend`:

```powershell
npm test -- src/views/LoginView.test.js
```

Expected: user test fails because the position selector does not exist.

- [ ] **Step 3: Implement the user-only selector and payload field**

In `LoginView.vue` add `const employmentType = ref('')`, include the user-only validation, and build the payload with a conditional spread:

```javascript
if (props.audience === 'user' && !employmentType.value) {
  ElMessage.error('请选择职位')
  return
}

const payload = {
  ...(useEmailLogin.value ? { email: email.value } : { username: username.value }),
  password: password.value,
  ...(props.audience === 'user' ? { employment_type: employmentType.value } : {}),
}
```

Add this field before the password input:

```vue
<label v-if="props.audience === 'user'" class="field">
  <span class="field-label">职位</span>
  <select v-model="employmentType" data-test="employment-type" class="field-input">
    <option disabled value="">请选择职位</option>
    <option value="intern">实习生</option>
    <option value="employee">正式员工</option>
  </select>
</label>
```

Display backend `message` or `error` in the catch branch:

```javascript
ElMessage.error(error.response?.data?.message || error.response?.data?.error || '登录失败')
```

- [ ] **Step 4: Run LoginView tests and verify GREEN**

Run:

```powershell
npm test -- src/views/LoginView.test.js
```

Expected: both user and administrator login tests pass.

---

### Task 4: Verify the User Workspace Learning Entry and Complete the Change

**Files:**
- Modify: `frontend/src/views/UserView.vue`
- Create: `frontend/src/views/UserView.test.js`
- Modify: `CLAUDE.md`
- Reference: `docs/superpowers/specs/2026-07-22-user-first-login-position-design.md`

**Interfaces:**
- Consumes: `/learning/me.can_view_learning_report`
- Produces: user-facing label `RPA 学习情况记录`

- [ ] **Step 1: Write a failing user-workspace entry test**

Create `frontend/src/views/UserView.test.js`:

```javascript
// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import UserView from './UserView.vue'

const api = vi.hoisted(() => ({ loadLearningProfile: vi.fn() }))
vi.mock('@/api/learning', () => api)
const ConsoleShell = {
  props: ['sections'],
  template: '<div><span v-for="section in sections" :key="section.path">{{ section.label }}</span></div>',
}

it('shows the RPA learning record entry to an eligible intern', async () => {
  api.loadLearningProfile.mockResolvedValue({ can_view_learning_report: true })
  const wrapper = mount(UserView, { global: { stubs: { ConsoleShell } } })
  await flushPromises()
  expect(wrapper.text()).toContain('RPA 学习情况记录')
})
```

- [ ] **Step 2: Run the UserView test and verify RED**

Run:

```powershell
npm test -- src/views/UserView.test.js
```

Expected: failure because the existing label is `学习周报`.

- [ ] **Step 3: Rename the eligible user entry and document the rule**

In `UserView.vue`, use:

```javascript
{ path: '/main/LearningReport', label: 'RPA 学习情况记录', desc: '保存本周学习草稿、正式提交并查看退回记录' }
```

Add to `CLAUDE.md`:

```markdown
- 用户端登录必须提交 `employment_type=intern|employee`。无 `user_roles` 映射时首次选择写入并固定；首次实习生立即加入当周名册。已有映射只校验不覆盖，职位不一致返回 `409`，后续仅 HR/老板可修改。
```

- [ ] **Step 4: Run all automated verification**

Run backend tests from `backend`:

```powershell
venv\Scripts\python.exe -m pytest tests -q
```

Run frontend tests and build from `frontend`:

```powershell
npm test
npm run build
```

Expected: all pytest and Vitest tests pass and Vite exits with code `0`.

- [ ] **Step 5: Restart local services and probe the live behavior**

Restart only the confirmed project-owned backend and frontend processes. Verify:

```text
GET http://127.0.0.1:5173/login -> 200
POST /user/login with first-time intern -> 200
GET /learning/me with returned token -> can_view_learning_report=true
GET /learning/me with returned token -> can_submit_current_week=true
```

Do not create or modify a real production MySQL user during the probe; use automated test fixtures for the credentialed flow.
