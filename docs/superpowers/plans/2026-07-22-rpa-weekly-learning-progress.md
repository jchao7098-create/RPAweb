# RPA Weekly Learning Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a role-protected weekly RPA learning report workflow for interns plus weekly statistics and role administration for HR and bosses.

**Architecture:** Keep MySQL `users` read-only and store roles, weekly roster snapshots, report drafts, immutable submissions, returns, and audits in the existing `assets.db` bind. Add a `/learning` Flask blueprint with signed-token authorization, then add three lazy-loaded Vue pages integrated into the existing user and admin consoles.

**Tech Stack:** Python 3.10+, Flask 3.1, Flask-SQLAlchemy 3.1, itsdangerous, SQLite, pytest; Vue 3, Vue Router 4, Axios, Element Plus, Vite 5, Vitest, Vue Test Utils, SVG.

## Global Constraints

- Treat MySQL `172.16.50.20/rpa_web` as read-only for this feature; never create, alter, or update MySQL tables.
- Store all new feature data in the existing `assets` bind at `backend/var/assets.db`.
- Use `Asia/Shanghai` for week boundaries and user-facing dates; store timestamps as naive UTC in SQLite.
- Roles are exactly `employee`, `intern`, `hr`, and `boss`; an unmapped user is `employee`.
- HR and boss permissions change immediately; weekly intern membership is frozen by a roster snapshot.
- Do not retrofit authentication onto existing non-learning routes.
- All frontend requests must use `frontend/src/api/http.js`; do not hard-code backend addresses.
- Keep routes lazy-loaded and reuse `frontend/src/assets/theme.css` shared classes.
- Do not import Element Plus APIs manually inside Vue components; existing auto-import configuration supplies them.
- Repository is not initialized as Git. Do not run `git init` without user approval. Each conditional commit step must print the documented skip message while `.git` is absent.
- Back up `backend/var/assets.db` before the first production-like startup that creates the new tables.

---

## File Structure

### Backend files

- Create `backend/app/models/learning.py`: seven SQLite models and role/state constants.
- Create `backend/app/learning/__init__.py`: learning package marker and public constants.
- Create `backend/app/learning/time.py`: UTC/Shanghai conversion, Monday boundaries, and deadline parsing.
- Create `backend/app/learning/errors.py`: typed API errors with HTTP status codes.
- Create `backend/app/learning/auth.py`: persistent token secret, token issue/verify, request decorators.
- Create `backend/app/learning/roles.py`: role lookup/change, bootstrap, roster snapshot, user merging, audit queries.
- Create `backend/app/learning/reports.py`: draft, immutable submission, history, locking, return, expiry.
- Create `backend/app/learning/stats.py`: weekly aggregates and personal trends.
- Create `backend/app/learning/serializers.py`: stable JSON shapes for reports, submissions, returns, users, and statistics.
- Create `backend/app/routes/learning.py`: thin HTTP layer for all `/learning` endpoints.
- Modify `backend/app/config.py`: token/bootstrap configuration.
- Modify `backend/app/__init__.py`: test configuration injection, model registration, blueprint registration, SQLite table creation, guarded startup bootstrap.
- Modify `backend/app/routes/user.py`: add learning token and role to successful user login.
- Modify `backend/app/routes/admin.py`: add learning token and role to successful admin login.
- Create `backend/requirements-dev.txt`: pytest test dependency.
- Create `backend/tests/conftest.py`: isolated dual-database app fixture.
- Create `backend/tests/test_learning_time_models.py`.
- Create `backend/tests/test_learning_auth.py`.
- Create `backend/tests/test_learning_roles.py`.
- Create `backend/tests/test_learning_reports.py`.
- Create `backend/tests/test_learning_stats.py`.

### Frontend files

- Create `frontend/src/utils/learningSession.js`: token/profile storage and permission helpers.
- Create `frontend/src/utils/learningSession.test.js`.
- Create `frontend/src/api/learning.js`: all learning endpoint wrappers.
- Create `frontend/src/components/user/LearningReport.vue`.
- Create `frontend/src/components/user/LearningReport.test.js`.
- Create `frontend/src/components/admin/LearningStats.vue`.
- Create `frontend/src/components/admin/LearningStats.test.js`.
- Create `frontend/src/components/admin/RoleManagement.vue`.
- Create `frontend/src/components/admin/RoleManagement.test.js`.
- Create `frontend/src/components/charts/LearningTrendChart.vue`.
- Create `frontend/src/components/charts/LearningTrendChart.test.js`.
- Modify `frontend/src/api/http.js`: attach/clear learning tokens only for learning requests.
- Modify `frontend/src/views/LoginView.vue`: persist token and role from either login audience.
- Modify `frontend/src/views/UserView.vue`: conditionally append “学习周报”.
- Modify `frontend/src/views/AdminView.vue`: conditionally append “学习统计” and “人员权限”.
- Modify `frontend/src/router/index.js`: lazy routes and learning-specific guard.
- Modify `frontend/package.json` and lockfile: Vitest test setup.
- Modify `README.md`, `CLAUDE.md`, and `DEPLOY.md`: configuration, data ownership, startup, and verification notes.

---

### Task 1: Test Harness, Time Utilities, and SQLite Schema

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_learning_time_models.py`
- Create: `backend/app/learning/__init__.py`
- Create: `backend/app/learning/time.py`
- Create: `backend/app/models/learning.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/__init__.py:8-44`

**Interfaces:**
- Produces: `utc_now() -> datetime`, `week_start_for(now_utc: datetime | None) -> date`, `week_end_utc(week_start: date) -> datetime`, `parse_shanghai_datetime(value: str) -> datetime`, `to_shanghai_iso(value: datetime | None) -> str | None`.
- Produces: `UserRole`, `RoleChangeLog`, `WeeklyRosterWeek`, `WeeklyRoster`, `WeeklyReport`, `WeeklyReportSubmission`, `ReportReturnLog`.
- Produces: `create_app(test_config: dict | None = None)` so later tasks can run without production MySQL.

- [ ] **Step 1: Add the isolated test dependency file**

```text
# backend/requirements-dev.txt
-r requirements.txt
pytest==8.3.5
```

- [ ] **Step 2: Install test dependencies**

Run from `D:\RPAweb\backend`:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Expected: installation succeeds and `.\venv\Scripts\python.exe -m pytest --version` prints `pytest 8.3.5`.

- [ ] **Step 3: Write failing time and schema tests**

```python
# backend/tests/test_learning_time_models.py
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError

from app import db
from app.learning.time import week_start_for
from app.models.learning import UserRole, WeeklyRosterWeek, WeeklyRoster


def test_week_start_uses_shanghai_timezone():
    assert week_start_for(datetime(2026, 7, 19, 16, 30)).isoformat() == '2026-07-20'


def test_empty_roster_week_is_persisted(app):
    with app.app_context():
        db.session.add(WeeklyRosterWeek(week_start=date(2026, 7, 20)))
        db.session.commit()
        assert WeeklyRosterWeek.query.count() == 1
        assert WeeklyRoster.query.count() == 0


def test_user_role_rejects_unknown_role(app):
    with app.app_context():
        db.session.add(UserRole(user_id=7, role='administrator'))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        else:
            raise AssertionError('unknown role was accepted')
```

The fixture must configure both databases without touching production:

```python
# backend/tests/conftest.py
import pytest

from app import create_app, db


@pytest.fixture()
def app(tmp_path):
    assets_path = (tmp_path / 'assets-test.db').as_posix()
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_BINDS': {'assets': f'sqlite:///{assets_path}'},
        'LEARNING_TOKEN_SECRET': 'test-learning-secret',
        'LEARNING_BOOTSTRAP_ON_STARTUP': False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
```

- [ ] **Step 4: Run tests and verify RED**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_learning_time_models.py -v
```

Expected: collection fails because `app.learning.time` and `app.models.learning` do not exist, or `create_app` rejects the test configuration argument.

- [ ] **Step 5: Implement the time API**

```python
# backend/app/learning/time.py
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo('Asia/Shanghai')


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _aware_utc(value):
    if value is None:
        value = utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def week_start_for(now_utc=None):
    local = _aware_utc(now_utc).astimezone(SHANGHAI)
    return local.date() - timedelta(days=local.weekday())


def week_end_utc(week_start):
    local_end = datetime.combine(week_start + timedelta(days=7), time.min, SHANGHAI)
    return local_end.astimezone(timezone.utc).replace(tzinfo=None)


def parse_shanghai_datetime(value):
    local = datetime.fromisoformat(value)
    if local.tzinfo is None:
        local = local.replace(tzinfo=SHANGHAI)
    else:
        local = local.astimezone(SHANGHAI)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def to_shanghai_iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).isoformat(timespec='seconds')
```

- [ ] **Step 6: Implement the seven assets-bind models**

Use `db.Integer` for `hours_tenths`, nullable report fields for incomplete drafts, unique constraints on `(week_start, user_id)`, and check constraints on every enum/range:

```python
# backend/app/models/learning.py
from app import db
from app.learning.time import utc_now

ROLES = ('employee', 'intern', 'hr', 'boss')
REPORT_STATES = ('draft', 'submitted', 'returned', 'return_expired')


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __bind_key__ = 'assets'
    user_id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(16), nullable=False)
    assigned_by_user_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = (db.CheckConstraint("role IN ('employee','intern','hr','boss')"),)


class RoleChangeLog(db.Model):
    __tablename__ = 'role_change_logs'
    __bind_key__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    target_user_id = db.Column(db.Integer, nullable=False, index=True)
    old_role = db.Column(db.String(16), nullable=False)
    new_role = db.Column(db.String(16), nullable=False)
    operator_user_id = db.Column(db.Integer)
    source = db.Column(db.String(16), nullable=False, default='manual')
    changed_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)


class WeeklyRosterWeek(db.Model):
    __tablename__ = 'weekly_roster_weeks'
    __bind_key__ = 'assets'
    week_start = db.Column(db.Date, primary_key=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class WeeklyRoster(db.Model):
    __tablename__ = 'weekly_rosters'
    __bind_key__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, db.ForeignKey('weekly_roster_weeks.week_start'), nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    __table_args__ = (db.UniqueConstraint('week_start', 'user_id'),)


class WeeklyReport(db.Model):
    __tablename__ = 'weekly_reports'
    __bind_key__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    content = db.Column(db.Text)
    hours_tenths = db.Column(db.Integer)
    completion = db.Column(db.Integer)
    remark = db.Column(db.Text)
    draft_revision = db.Column(db.Integer, default=0, nullable=False)
    latest_submission_id = db.Column(db.Integer)
    state = db.Column(db.String(24), default='draft', nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = (
        db.UniqueConstraint('week_start', 'user_id'),
        db.CheckConstraint("state IN ('draft','submitted','returned','return_expired')"),
        db.CheckConstraint('hours_tenths IS NULL OR (hours_tenths >= 0 AND hours_tenths <= 1680)'),
        db.CheckConstraint('completion IS NULL OR (completion >= 0 AND completion <= 100)'),
    )


class WeeklyReportSubmission(db.Model):
    __tablename__ = 'weekly_report_submissions'
    __bind_key__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('weekly_reports.id'), nullable=False, index=True)
    source_revision = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    hours_tenths = db.Column(db.Integer, nullable=False)
    completion = db.Column(db.Integer, nullable=False)
    remark = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class ReportReturnLog(db.Model):
    __tablename__ = 'report_return_logs'
    __bind_key__ = 'assets'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('weekly_reports.id'), nullable=False, index=True)
    returned_by_user_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    edit_deadline = db.Column(db.DateTime, nullable=False)
    returned_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    resubmitted_at = db.Column(db.DateTime)
```

- [ ] **Step 7: Make the app factory testable and register the models before `create_all`**

Change the signature to `create_app(test_config=None)`, apply `app.config.update(test_config)` after the normal config, import `app.models.learning` before creating assets tables, and keep startup side effects guarded by `LEARNING_BOOTSTRAP_ON_STARTUP` for later tasks.

```python
def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    from app.models import learning as _learning_models
    # existing blueprint registration follows
```

- [ ] **Step 8: Run model tests and the existing backend import smoke check**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_learning_time_models.py -v
.\venv\Scripts\python.exe -c "from app import create_app; print(create_app({'TESTING': True, 'LEARNING_BOOTSTRAP_ON_STARTUP': False}).name)"
```

Expected: all tests pass; smoke check prints `app` without touching MySQL.

- [ ] **Step 9: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add app/config.py app/__init__.py app/learning app/models/learning.py tests requirements-dev.txt
  git commit -m "feat: add learning data model and test harness"
} else {
  Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.'
}
```

Expected now: `SKIP COMMIT: D:\RPAweb is not initialized as Git.`

---

### Task 2: Signed Learning Tokens and Login Integration

**Files:**
- Create: `backend/app/learning/errors.py`
- Create: `backend/app/learning/roles.py`
- Create: `backend/app/learning/auth.py`
- Create: `backend/tests/test_learning_auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/routes/user.py:12-35`
- Modify: `backend/app/routes/admin.py:22-45`

**Interfaces:**
- Consumes: `UserRole`, `utc_now()`.
- Produces: `get_role(user_id: int) -> str`, returning `employee` when no mapping exists.
- Produces: `ensure_learning_token_secret(app) -> str`, `issue_learning_token(user_id: int) -> str`, `decode_learning_token(token: str) -> int`, `learning_auth_required`, `learning_roles_required(*roles)`, `learning_login_fields(user_id: int) -> dict`.

- [ ] **Step 1: Write failing token and login tests**

```python
# backend/tests/test_learning_auth.py
from app import db
from app.models.models import User
from app.models.learning import UserRole


def test_user_login_returns_learning_token_and_default_role(client, app):
    with app.app_context():
        db.session.add(User(username='worker', email='worker@example.com', password='secret1'))
        db.session.commit()
    response = client.post('/user/login', json={'username': 'worker', 'password': 'secret1'})
    assert response.status_code == 200
    assert response.json['learning_role'] == 'employee'
    assert response.json['learning_token']


def test_token_rejects_tampering(client, app):
    with app.app_context():
        db.session.add(User(username='intern', email='intern@example.com', password='secret1'))
        db.session.flush()
        user_id = User.query.filter_by(username='intern').one().id
        db.session.add(UserRole(user_id=user_id, role='intern'))
        db.session.commit()
    response = client.get('/learning/me', headers={'Authorization': 'Bearer broken.token'})
    assert response.status_code == 401
```

- [ ] **Step 2: Run the auth tests and verify RED**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_learning_auth.py -v`

Expected: login response lacks `learning_token`, and `/learning/me` returns 404 until later route registration.

- [ ] **Step 3: Add exact token configuration**

```python
# additions in backend/app/config.py
LEARNING_TOKEN_SECRET = os.environ.get('LEARNING_TOKEN_SECRET')
LEARNING_TOKEN_SECRET_FILE = os.path.join(_VAR_DIR, 'learning_token_secret.key')
LEARNING_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('LEARNING_TOKEN_MAX_AGE_SECONDS', '43200'))
INITIAL_BOSS_EMAILS = os.environ.get('INITIAL_BOSS_EMAILS', '')
LEARNING_BOOTSTRAP_ON_STARTUP = True
```

- [ ] **Step 4: Implement typed errors, default role lookup, secret persistence, and token decorators**

Create `errors.py` with `LearningError`, `LearningValidationError`, `LearningConflictError`, `LearningForbiddenError`, `LearningNotFoundError`, and `LearningUnauthorizedError` using status codes `400/422/409/403/404/401`. Create `roles.py` with the exact default lookup below; Task 3 extends the same file.

```python
def get_role(user_id):
    row = UserRole.query.filter_by(user_id=int(user_id)).first()
    return row.role if row else 'employee'
```

`auth.py` must use `URLSafeTimedSerializer`, salt `rpa-learning-v1`, a `learning` purpose claim, and `secrets.token_urlsafe(48)` for the persisted fallback secret. `decode_learning_token` must raise `LearningUnauthorizedError` on missing, expired, malformed, or wrong-purpose tokens. The request decorator stores the verified integer in `g.learning_user_id`.

```python
def learning_login_fields(user_id):
    from app.learning.roles import get_role
    return {
        'learning_token': issue_learning_token(user_id),
        'learning_role': get_role(user_id),
    }
```

- [ ] **Step 5: Add the token fields to both successful login responses**

```python
payload = {'message': '登录成功', 'user_id': user.id}
payload.update(learning_login_fields(user.id))
return jsonify(payload), 200
```

Use `admin_id` in the admin payload but the same `learning_login_fields` helper.

- [ ] **Step 6: Add a minimal authenticated `/learning/me` probe for the token tests**

Create `backend/app/routes/learning.py` with a `learning_bp`, a blueprint error handler for typed learning errors, and `GET /me` returning `{'user_id': g.learning_user_id}`. Register it at `/learning` in `create_app`.

- [ ] **Step 7: Run auth tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_learning_auth.py -v`

Expected: token/login tests pass, including `401` for tampering.

- [ ] **Step 8: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add app/config.py app/learning/errors.py app/learning/roles.py app/learning/auth.py app/routes/user.py app/routes/admin.py app/routes/learning.py app/__init__.py tests/test_learning_auth.py
  git commit -m "feat: issue signed learning tokens"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 3: Roles, Weekly Roster Snapshots, and Role Administration

**Files:**
- Modify: `backend/app/learning/roles.py`
- Create: `backend/tests/test_learning_roles.py`
- Modify: `backend/app/routes/learning.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: `get_role(user_id: int) -> str` from Task 2.
- Produces: `ensure_roster_week(week_start: date | None = None) -> WeeklyRosterWeek`, `is_roster_member(user_id: int, week_start: date) -> bool`, `get_identity(user_id: int) -> dict`, `bootstrap_initial_bosses() -> int`, `change_role(target_user_id: int, new_role: str, operator_user_id: int, week_start: date | None = None) -> dict`.
- Produces endpoints: `GET /learning/me`, `GET /learning/admin/users`, `PATCH /learning/admin/users/<id>/role`, `GET /learning/admin/role-change-logs`.

- [ ] **Step 1: Write failing role and roster tests**

Cover these exact cases in `test_learning_roles.py`:

```python
def test_empty_week_stays_frozen_after_midweek_intern_assignment(app):
    with app.app_context():
        week = ensure_roster_week(date(2026, 7, 20))
        change_role(target_user_id=2, new_role='intern', operator_user_id=1,
                    week_start=date(2026, 7, 20))
        assert WeeklyRoster.query.filter_by(week_start=week.week_start).count() == 0


def test_role_change_is_audited_in_same_transaction(app):
    result = change_role(target_user_id=2, new_role='hr', operator_user_id=1)
    assert result['old_role'] == 'employee'
    assert RoleChangeLog.query.filter_by(target_user_id=2).one().new_role == 'hr'


def test_hr_can_assign_boss(client, hr_headers):
    response = client.patch('/learning/admin/users/2/role', json={'role': 'boss'}, headers=hr_headers)
    assert response.status_code == 200
    assert response.json['role'] == 'boss'
```

Fixtures must create real `User` rows in the test main SQLite and issue tokens with `issue_learning_token`.

- [ ] **Step 2: Run role tests and verify RED**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_learning_roles.py -v`

Expected: import errors for `app.learning.roles` and 404 for role endpoints.

- [ ] **Step 3: Extend the existing role service with roster and administration APIs**

Keep Task 2's `get_role` unchanged. Add the roster, bootstrap, identity, change, user-list, and audit functions to the same focused module; use the typed errors already created in Task 2.

- [ ] **Step 4: Implement roster freezing before every role change**

`ensure_roster_week` must first query `WeeklyRosterWeek` by the Monday date. If present, return it without adding members. If absent, insert the header and one member for every current `UserRole(role='intern')`, then flush. This header-first rule is what freezes a zero-person week.

- [ ] **Step 5: Implement role lookup, bootstrap, and transactional change**

`get_role` returns `employee` for no row. `change_role` validates the target in MySQL, validates the role constant, ensures the current roster before writing, upserts `UserRole`, inserts `RoleChangeLog(source='manual')`, commits once, and returns old/new role. Same-role requests return the current role without adding a false audit entry.

`bootstrap_initial_bosses` parses trimmed lowercase emails, queries matching MySQL users in one query, creates only missing mappings, adds `source='bootstrap'` audits, and commits once. It must not overwrite an existing role.

- [ ] **Step 6: Replace the minimal `/learning/me` response and add admin routes**

`GET /learning/me` returns:

```json
{
  "user_id": 2,
  "role": "intern",
  "week_start": "2026-07-20",
  "week_end": "2026-07-26",
  "is_current_roster_member": true,
  "can_view_learning_report": true,
  "can_submit_current_week": true,
  "can_manage_learning": false
}
```

Protect user list, role patch, and audit endpoints with `@learning_roles_required('hr', 'boss')`. Batch-merge user display data from MySQL; never serialize `password`.

- [ ] **Step 7: Add guarded startup initialization**

After `db.create_all(bind_key='assets')`, call `ensure_learning_token_secret`, `bootstrap_initial_bosses`, and `ensure_roster_week` only when `LEARNING_BOOTSTRAP_ON_STARTUP` is true. Catch bootstrap MySQL connectivity errors, log a concise warning, and keep the server alive; login will still report database errors through existing behavior.

- [ ] **Step 8: Run role tests and all backend tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_learning_roles.py -v
.\venv\Scripts\python.exe -m pytest -q
```

Expected: role tests pass; all backend tests pass.

- [ ] **Step 9: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add app/learning/roles.py app/routes/learning.py app/__init__.py tests/test_learning_roles.py
  git commit -m "feat: add learning role and roster management"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 4: Intern Drafts, Immutable Submissions, History, and Optimistic Concurrency

**Files:**
- Create: `backend/app/learning/reports.py`
- Create: `backend/app/learning/serializers.py`
- Create: `backend/tests/test_learning_reports.py`
- Modify: `backend/app/routes/learning.py`

**Interfaces:**
- Produces: `get_current_report(user_id, now_utc=None)`, `save_draft(user_id, payload, expected_revision, report_id=None, now_utc=None)`, `submit_report(user_id, expected_revision, report_id=None, now_utc=None)`, `list_history(user_id, from_week=None, to_week=None)`, `serialize_report(report, now_utc=None)`.
- Produces current and historical report endpoints defined in the design spec.

- [ ] **Step 1: Write failing lifecycle tests**

`test_learning_reports.py` must prove:

```python
def test_draft_is_not_a_submission(app, intern_id):
    report = save_draft(intern_id, {'content': '', 'hours': None, 'completion': None, 'remark': ''}, 0)
    assert report.state == 'draft'
    assert report.latest_submission_id is None


def test_submitted_edit_keeps_previous_formal_version(app, intern_id):
    report = save_draft(intern_id, {'content': '基础学习', 'hours': 12.5, 'completion': 60, 'remark': ''}, 0)
    submit_report(intern_id, report.draft_revision)
    old_submission_id = report.latest_submission_id
    save_draft(intern_id, {'content': '进阶学习', 'hours': 16, 'completion': 75, 'remark': ''}, report.draft_revision)
    assert report.latest_submission_id == old_submission_id
    assert serialize_report(report)['has_unsubmitted_changes'] is True


def test_revision_conflict_is_409(app, intern_id):
    report = save_draft(intern_id, {'content': 'A'}, 0)
    with pytest.raises(LearningConflictError):
        save_draft(intern_id, {'content': 'B'}, 0)
```

Also test 0/168 hours, a rejected second decimal, 0/100 completion, Monday locking, non-roster denial, and own-report-only historical access.

- [ ] **Step 2: Run report tests and verify RED**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_learning_reports.py -v`

Expected: import errors for `app.learning.reports`.

- [ ] **Step 3: Implement draft normalization and final validation**

Use `Decimal(str(hours)) * 10`; reject a non-integral result. Drafts may contain empty/null values. Formal submission requires trimmed content, hours, and completion. Never trust a client-supplied `user_id`, week, state, or latest submission ID.

- [ ] **Step 4: Implement current-week editability and optimistic revisions**

Current reports are editable only while `now_utc < week_end_utc(report.week_start)` and the authenticated user is in that week roster. A new report starts at revision 0; every successful draft save increments it. Reject a mismatched `expected_revision` with `LearningConflictError('记录已在其他页面更新，请刷新后重试')`.

- [ ] **Step 5: Implement immutable submissions**

Within one transaction: validate the working copy, insert `WeeklyReportSubmission(source_revision=report.draft_revision, ...)`, flush for its ID, set `report.latest_submission_id`, set `state='submitted'`, and commit. Never update an existing submission row.

- [ ] **Step 6: Implement history and historical returned-record edit paths**

The three `<report_id>` endpoints must verify ownership. Draft/submit is allowed only while state is `returned` and `now_utc < latest unresolved return.edit_deadline`; successful resubmission sets that return log’s `resubmitted_at`, state `submitted`, and remains locked because the report week is historical.

- [ ] **Step 7: Add stable serializers**

`serialize_report` returns decimal hours, current work copy, latest formal snapshot, `draft_revision`, `has_unsubmitted_changes`, computed editability, display status, and ordered return history with Shanghai timestamps. Do not leak another user’s data.

- [ ] **Step 8: Add routes and HTTP status behavior**

Add exact routes from design section 8.1. Use `201` for the first report creation, `200` for updates/submissions, `403` for roster/ownership, `409` for state/revision conflicts, and `422` for field errors.

- [ ] **Step 9: Run report tests and full backend suite**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_learning_reports.py -v
.\venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 10: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add app/learning/reports.py app/learning/serializers.py app/routes/learning.py tests/test_learning_reports.py
  git commit -m "feat: add weekly learning report lifecycle"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 5: Weekly Statistics, Personal Trends, Returns, and Expiry

**Files:**
- Create: `backend/app/learning/stats.py`
- Create: `backend/tests/test_learning_stats.py`
- Modify: `backend/app/learning/reports.py`
- Modify: `backend/app/learning/serializers.py`
- Modify: `backend/app/routes/learning.py`

**Interfaces:**
- Produces: `weekly_stats(week_start: date) -> dict`, `user_trend(user_id: int, from_week: date | None, to_week: date | None) -> dict`, `return_report(report_id: int, operator_id: int, reason: str, edit_deadline: str, now_utc=None) -> WeeklyReport`, `expire_return_if_needed(report, now_utc=None) -> bool`.

- [ ] **Step 1: Write failing statistics and return tests**

Prove all of these in `test_learning_stats.py`:

- roster count is the denominator;
- draft, missing, returned, and expired reports are unsubmitted;
- total hours and average completion use only valid latest submissions;
- zero submissions yield `average_completion is None`;
- a returned report is excluded until resubmission;
- expiry changes state to `return_expired` and supports another return;
- default trend contains 12 Monday buckets and gaps for excluded reports;
- deadline must be future Shanghai time and reason must be non-empty.

Core assertion:

```python
result = weekly_stats(date(2026, 7, 20))
assert result['submitted_count'] == 2
assert result['unsubmitted_count'] == 1
assert result['total_hours'] == 30.5
assert result['average_completion'] == 75.0
```

- [ ] **Step 2: Run stats tests and verify RED**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_learning_stats.py -v`

Expected: import errors for `app.learning.stats` and missing return service.

- [ ] **Step 3: Implement batched weekly aggregation**

Load roster user IDs in one assets query, reports in one query, latest submissions in one `IN` query, and display users in one MySQL query. Build a row for every roster member. Do not issue per-user SQL. Convert `hours_tenths` only after integer summation.

- [ ] **Step 4: Implement 12-week/default and custom-range trends**

Default `to_week` is the current Monday and `from_week` is 11 weeks earlier. Validate both values are Mondays and `from_week <= to_week`. Return every Monday bucket so the SVG shows gaps instead of compressing missing weeks.

- [ ] **Step 5: Implement return and lazy expiry transitions**

Return only historical reports with a latest formal version. Reset work-copy fields and `draft_revision` to the formal snapshot, insert a new return log, set state `returned`, and commit once. `expire_return_if_needed` changes `returned` to `return_expired` when the deadline has passed and commits only if it changed.

- [ ] **Step 6: Add protected admin routes**

Add weekly stats, trend, and return endpoints under `/learning/admin`, protected by HR/boss role decorator. Return `422` for malformed week/deadline and `409` for an ineligible report state.

- [ ] **Step 7: Run stats tests, SQL-count assertion, and full backend suite**

Add an SQL event counter test that compares a 2-person roster with a 20-person roster and asserts both executions use at most six SQL statements. Then run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_learning_stats.py -v
.\venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass and both SQL-count measurements are `<= 6`.

- [ ] **Step 8: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add app/learning/stats.py app/learning/reports.py app/learning/serializers.py app/routes/learning.py tests/test_learning_stats.py
  git commit -m "feat: add learning statistics and return workflow"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 6: Frontend Session, API Client, Route Guards, and Role-Aware Navigation

**Files:**
- Create: `frontend/src/utils/learningSession.js`
- Create: `frontend/src/utils/learningSession.test.js`
- Create: `frontend/src/api/learning.js`
- Modify: `frontend/src/api/http.js`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/UserView.vue`
- Modify: `frontend/src/views/AdminView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**
- Produces from `learningSession.js`: `getLearningToken`, `setLearningSession`, `clearLearningSession`, `getCachedLearningProfile`, `setCachedLearningProfile`, `canViewReport`, and `canManageLearning` without importing the API layer.
- Produces from `api/learning.js`: `loadLearningProfile`, `fetchLearningMe`, `fetchCurrentReport`, `saveCurrentDraft`, `submitCurrentReport`, `fetchReportHistory`, `fetchReport`, `saveReturnedDraft`, `submitReturnedReport`, `fetchWeeklyStats`, `fetchUserTrend`, `returnLearningReport`, `fetchLearningUsers`, `changeLearningRole`, and `fetchRoleChangeLogs`.

- [ ] **Step 1: Install frontend test tooling and add scripts**

Run from `D:\RPAweb\frontend`:

```powershell
npm install --save-dev vitest@2.1.9 @vue/test-utils@2.4.6 jsdom@25.0.1
```

Add scripts:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 2: Write failing session/access tests**

```javascript
import { beforeEach, describe, expect, it } from 'vitest'
import { clearLearningSession, getLearningToken, setLearningSession, canViewReport, canManageLearning } from './learningSession'

describe('learningSession', () => {
  beforeEach(() => localStorage.clear())
  it('stores and clears token', () => {
    setLearningSession({ token: 'signed', role: 'intern' })
    expect(getLearningToken()).toBe('signed')
    clearLearningSession()
    expect(getLearningToken()).toBe('')
  })
  it('uses server capability flags', () => {
    expect(canViewReport({ can_view_learning_report: true })).toBe(true)
    expect(canManageLearning({ can_manage_learning: true })).toBe(true)
  })
})
```

- [ ] **Step 3: Run tests and verify RED**

Run: `npm test -- src/utils/learningSession.test.js`

Expected: module-not-found failure.

- [ ] **Step 4: Implement session and API wrappers**

Use localStorage keys `learning_token`, `learning_role`, and `learning_profile`. Keep storage helpers independent from Axios to avoid an `http.js -> learningSession.js -> learning.js -> http.js` import cycle. Implement `loadLearningProfile` in `api/learning.js`; it calls `GET /learning/me`, refreshes the cache, and never treats cached role as authoritative.

`frontend/src/api/learning.js` exports one named function per design endpoint, including historical report draft/submit and role audit pagination. Components must not build URLs themselves.

- [ ] **Step 5: Add request/response interceptors to the shared Axios instance**

Only URLs beginning with `/learning` receive the Bearer header. On a learning `401`, call `clearLearningSession`; leave all existing non-learning requests unchanged.

- [ ] **Step 6: Persist token and role after either login**

After the existing ID storage in `LoginView.vue`, call:

```javascript
setLearningSession({
  token: res.data.learning_token,
  role: res.data.learning_role,
})
```

- [ ] **Step 7: Add lazy routes and server-backed guard**

Add child route metadata:

```javascript
meta: { learningAudience: 'report' }
meta: { learningAudience: 'admin' }
```

The `beforeEach` guard calls `loadLearningProfile({ force: true })`; allow `report` only when `can_view_learning_report`, and `admin` only when `can_manage_learning`. Redirect unauthenticated users to the appropriate existing login route and forbidden users to their console root.

- [ ] **Step 8: Make console sections dynamic**

Keep existing section arrays unchanged, load the learning profile on mount, and append exactly one user card or two admin cards based on server flags. Do not show learning cards while identity loading fails.

- [ ] **Step 9: Run frontend tests and production build**

Run:

```powershell
npm test -- src/utils/learningSession.test.js
npm run build
```

Expected: tests pass and Vite build completes without warnings about unresolved imports.

- [ ] **Step 10: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add package.json package-lock.json src/api/http.js src/api/learning.js src/utils/learningSession.js src/utils/learningSession.test.js src/views/LoginView.vue src/views/UserView.vue src/views/AdminView.vue src/router/index.js
  git commit -m "feat: add learning frontend access control"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 7: Intern Learning Report Page

**Files:**
- Create: `frontend/src/components/user/LearningReport.vue`
- Create: `frontend/src/components/user/LearningReport.test.js`

**Interfaces:**
- Consumes: `fetchCurrentReport`, `saveCurrentDraft`, `submitCurrentReport`, `fetchReportHistory`, `fetchReport`, `saveReturnedDraft`, `submitReturnedReport` from `api/learning.js`.
- Produces: user-facing current report form and historical returned report editor.

- [ ] **Step 1: Write failing component tests**

Mock `api/learning.js` and assert:

1. draft save sends `expected_revision` and keeps form values on 422;
2. formal submit shows success and reloads current report;
3. “有未提交修改” appears from server flag;
4. returned reason/deadline appears and a historical returned report can be edited;
5. locked/non-roster states disable both actions.

Example:

```javascript
it('sends the server revision when saving a draft', async () => {
  const wrapper = mount(LearningReport)
  await flushPromises()
  await wrapper.find('[data-test="content"]').setValue('学习 UiPath')
  await wrapper.find('[data-test="save-draft"]').trigger('click')
  expect(saveCurrentDraft).toHaveBeenCalledWith(expect.objectContaining({ expected_revision: 3 }))
})
```

- [ ] **Step 2: Run the component test and verify RED**

Run: `npm test -- src/components/user/LearningReport.test.js`

Expected: component-not-found failure.

- [ ] **Step 3: Implement the current-week form**

Use `admin-page`, `panel`, `chip`, and existing form tokens. Bind `content`, `hours`, `completion`, and `remark`; send server revision on both actions. Treat frontend validation as convenience only. Buttons use separate loading flags and never clear the form on an error.

- [ ] **Step 4: Implement state banners and immutable-version details**

Render distinct banners for draft, submitted, unsubmitted changes, locked unsubmitted, returned, and return expired. Show the latest formal version separately when the working copy differs.

- [ ] **Step 5: Implement history and returned-record editing**

Render history newest-first. Expanding an entry shows the formal version and all return logs. If server says the historical report is editable, reuse the same field component with the `<report_id>` API wrappers; successful resubmit closes the editor and reloads history.

- [ ] **Step 6: Run component tests and build**

Run:

```powershell
npm test -- src/components/user/LearningReport.test.js
npm run build
```

Expected: tests and build pass.

- [ ] **Step 7: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add src/components/user/LearningReport.vue src/components/user/LearningReport.test.js
  git commit -m "feat: add intern weekly learning report page"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 8: HR/Boss Weekly Statistics and SVG Trend Chart

**Files:**
- Create: `frontend/src/components/charts/LearningTrendChart.vue`
- Create: `frontend/src/components/charts/LearningTrendChart.test.js`
- Create: `frontend/src/components/admin/LearningStats.vue`
- Create: `frontend/src/components/admin/LearningStats.test.js`

**Interfaces:**
- Consumes: `fetchWeeklyStats`, `fetchUserTrend`, `returnLearningReport`.
- Produces: approved vertical dashboard layout and combined bars/line SVG chart.

- [ ] **Step 1: Write failing chart and dashboard tests**

Chart tests assert one bar per non-null hours value, a completion polyline, and an accessible empty state. Dashboard tests assert the four KPI values, roster rows, trend load on row selection, and mandatory return reason/deadline.

```javascript
expect(wrapper.findAll('[data-test="hours-bar"]')).toHaveLength(3)
expect(wrapper.find('[data-test="completion-line"]').attributes('points')).toContain(',')
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
npm test -- src/components/charts/LearningTrendChart.test.js src/components/admin/LearningStats.test.js
```

Expected: component-not-found failures.

- [ ] **Step 3: Implement the dependency-free SVG chart**

Compute a shared x-axis, a left hours scale, and a right completion scale fixed at 0–100. Use `<rect>` for hours and `<polyline>` plus circles for completion. Gaps must omit points rather than interpolate excluded weeks. Add `role="img"` and a Chinese `aria-label`.

- [ ] **Step 4: Implement the approved A-layout dashboard**

Order elements exactly: page header and Monday-normalized week picker; four KPI cards; roster table; selected-person trend below the table. Normalize any picked date to Monday with `(day + 6) % 7` rather than Sunday-based `startOf('week')`.

- [ ] **Step 5: Implement return dialog validation**

Only rows with server `can_return` show the action. Require trimmed reason and a deadline later than now; send an ISO local date-time. On success reload both weekly stats and selected trend.

- [ ] **Step 6: Run tests and build**

Run:

```powershell
npm test -- src/components/charts/LearningTrendChart.test.js src/components/admin/LearningStats.test.js
npm run build
```

Expected: tests and build pass.

- [ ] **Step 7: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add src/components/charts/LearningTrendChart.vue src/components/charts/LearningTrendChart.test.js src/components/admin/LearningStats.vue src/components/admin/LearningStats.test.js
  git commit -m "feat: add weekly learning statistics dashboard"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 9: HR/Boss Role Management and Audit Page

**Files:**
- Create: `frontend/src/components/admin/RoleManagement.vue`
- Create: `frontend/src/components/admin/RoleManagement.test.js`

**Interfaces:**
- Consumes: `fetchLearningUsers`, `changeLearningRole`, `fetchRoleChangeLogs`.
- Produces: paginated personnel search, all-role selector, confirmation flow, audit viewer.

- [ ] **Step 1: Write failing role management tests**

Assert default `employee` labels, search/pagination parameters, all four select options, confirmation before PATCH, refresh after success, same-role no-op, and audit columns for target/operator/old/new/time.

- [ ] **Step 2: Run tests and verify RED**

Run: `npm test -- src/components/admin/RoleManagement.test.js`

Expected: component-not-found failure.

- [ ] **Step 3: Implement personnel search and role updates**

Use a debounced search field and server pagination. Keep the selected role local until confirmation. HR and boss both see all four role choices. After success update the row from server response and reload the audit page.

- [ ] **Step 4: Implement role audit table**

Show target user, original role, new role, operator, source, and Shanghai time. Render bootstrap operator as “系统初始化”. Provide independent audit pagination so user search does not reset audit position.

- [ ] **Step 5: Run tests and build**

Run:

```powershell
npm test -- src/components/admin/RoleManagement.test.js
npm run build
```

Expected: tests and build pass.

- [ ] **Step 6: Conditional commit**

```powershell
if (Test-Path -LiteralPath '..\.git') {
  git add src/components/admin/RoleManagement.vue src/components/admin/RoleManagement.test.js
  git commit -m "feat: add learning role administration"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

---

### Task 10: Documentation, Full Regression, Local Migration, and Browser Verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `DEPLOY.md`
- Verify: all files from Tasks 1–9

**Interfaces:**
- Consumes: complete backend and frontend feature.
- Produces: operationally documented and verified module with a recoverable SQLite backup.

- [ ] **Step 1: Update documentation with exact runtime configuration**

Document `INITIAL_BOSS_EMAILS`, optional `LEARNING_TOKEN_SECRET`, 12-hour default token age, `assets.db` table ownership, backup command, and the three new routes. State explicitly that existing non-learning admin routes retain their previous authentication behavior.

- [ ] **Step 2: Run complete automated verification**

```powershell
Set-Location 'D:\RPAweb\backend'
.\venv\Scripts\python.exe -m pytest -q
Set-Location 'D:\RPAweb\frontend'
npm test
npm run build
```

Expected: all backend tests pass; all Vitest tests pass; Vite build exits 0.

- [ ] **Step 3: Back up the exact SQLite database before table creation**

```powershell
$assetDb = (Resolve-Path -LiteralPath 'D:\RPAweb\backend\var\assets.db').Path
$backup = "$assetDb.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $assetDb -Destination $backup
Get-Item -LiteralPath $assetDb,$backup | Select-Object FullName,Length
```

Expected: source and backup exist with identical byte lengths before restart.

- [ ] **Step 4: Configure a real initial boss without hard-coding identity**

Before starting the backend, obtain one approved existing account email from the user, then set it only in the process environment:

```powershell
$approvedBossEmail = Read-Host '请输入已批准的首个老板账号邮箱'
$env:INITIAL_BOSS_EMAILS = $approvedBossEmail
```

Expected: the variable contains the explicitly approved email; no email is written into source control.

- [ ] **Step 5: Restart backend and frontend using validated project paths**

Stop only the exact existing RPAweb listener process trees, restart `backend\venv\Scripts\python.exe run.py` and `npm.cmd run dev -- --host 0.0.0.0` with hidden windows and timestamped logs, then verify:

```powershell
curl.exe -sS -o NUL -w "backend %{http_code}`n" http://127.0.0.1:5000/public/ping
curl.exe -sS -o NUL -w "frontend %{http_code}`n" http://127.0.0.1:5173/
```

Expected: both return `200`.

- [ ] **Step 6: Verify SQLite changed and MySQL did not**

Use SQLAlchemy inspection to assert the seven new SQLite tables exist. Capture the MySQL `users` column list before and after and assert it remains exactly `id, username, email, password, created_at`.

- [ ] **Step 7: Browser-test all four roles**

Using explicitly approved existing test accounts:

1. ordinary employee: no learning menus; direct URLs denied;
2. intern/current roster member: draft, submit, edit-after-submit, history;
3. HR: stats, trend, return, role management, audit;
4. boss: same administration capabilities as HR.

Also verify returned editing, expiry messaging, 401 re-login, 403 redirect, 409 refresh prompt, and 422 form preservation.

- [ ] **Step 8: Conditional final commit**

```powershell
if (Test-Path -LiteralPath 'D:\RPAweb\.git') {
  git -C 'D:\RPAweb' add README.md CLAUDE.md DEPLOY.md backend frontend docs/superpowers
  git -C 'D:\RPAweb' commit -m "feat: add weekly RPA learning progress module"
} else { Write-Output 'SKIP COMMIT: D:\RPAweb is not initialized as Git.' }
```

Expected now: skip message. Do not initialize Git automatically.

---

## Final Acceptance Checklist

- [ ] Every backend test passes against isolated databases.
- [ ] Every frontend unit test passes.
- [ ] `npm run build` passes.
- [ ] MySQL schema and data remain unchanged by the feature.
- [ ] Existing `assets.db` has a verified timestamped backup.
- [ ] All seven new SQLite tables exist after startup.
- [ ] Ordinary users cannot see or call learning endpoints.
- [ ] Intern draft/submission/version/locking behavior matches the design.
- [ ] HR/boss stats, trends, returns, role changes, and audits work end-to-end.
- [ ] Current-week roster stays stable across midweek role changes, including a zero-intern week.
- [ ] All user-facing dates use `Asia/Shanghai`.
