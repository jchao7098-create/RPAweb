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
    __table_args__ = (
        db.CheckConstraint("old_role IN ('employee','intern','hr','boss')"),
        db.CheckConstraint("new_role IN ('employee','intern','hr','boss')"),
    )


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
    record_date = db.Column(db.Date)
    certificate = db.Column(db.String(64))
    program_count = db.Column(db.Integer)
    blockers = db.Column(db.Text)
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
        db.CheckConstraint('program_count IS NULL OR (program_count >= 0 AND program_count <= 9999)'),
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
    record_date = db.Column(db.Date)
    certificate = db.Column(db.String(64))
    program_count = db.Column(db.Integer)
    blockers = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    __table_args__ = (
        db.CheckConstraint('hours_tenths >= 0 AND hours_tenths <= 1680'),
        db.CheckConstraint('completion >= 0 AND completion <= 100'),
        db.CheckConstraint('program_count IS NULL OR (program_count >= 0 AND program_count <= 9999)'),
    )


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
