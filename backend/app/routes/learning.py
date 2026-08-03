from datetime import date

from flask import Blueprint, Response, g, jsonify, request

from app.learning.auth import learning_auth_required, learning_roles_required, learning_surface_required
from app.learning.errors import LearningError, LearningValidationError
from app.learning.exports import recent_week_csv
from app.learning.roles import change_role, get_identity, list_role_change_logs, list_users
from app.learning.reports import get_current_report, get_report, return_report, save_draft, submit_report, list_history
from app.learning.serializers import serialize_report
from app.learning.stats import submission_history, user_history, user_trend, weekly_stats
from app.learning.time import week_start_for
from app.models.learning import WeeklyReport


learning_bp = Blueprint('learning', __name__)


@learning_bp.errorhandler(LearningError)
def handle_learning_error(error):
    return jsonify({'error': error.message}), error.status_code


@learning_bp.route('/me', methods=['GET'])
@learning_auth_required
def me():
    return jsonify(get_identity(g.learning_user_id, g.learning_login_surface))


def _json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LearningValidationError('JSON object is required')
    return payload


def _week_query(name, default=None):
    value = request.args.get(name)
    if not value:
        return default
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise LearningValidationError(f'{name} must be YYYY-MM-DD')
    if parsed.weekday() != 0:
        raise LearningValidationError(f'{name} must be a Monday')
    return parsed


def _serialize_stats_dates(payload):
    payload = dict(payload)
    for field in ('week_start', 'from_week', 'to_week'):
        if field in payload and payload[field] is not None:
            payload[field] = payload[field].isoformat()
    for collection in ('points', 'rows', 'items'):
        if collection not in payload:
            continue
        source_rows = payload[collection]
        payload[collection] = []
        for source in source_rows:
            row = dict(source)
            for field in ('week_start', 'record_date'):
                if field in row and row[field] is not None and hasattr(row[field], 'isoformat'):
                    row[field] = row[field].isoformat()
            payload[collection].append(row)
    return payload


@learning_bp.route('/reports/current', methods=['GET'])
@learning_surface_required('user')
def current_report():
    return jsonify(serialize_report(get_current_report(g.learning_user_id)))


@learning_bp.route('/reports/current/draft', methods=['PUT'])
@learning_surface_required('user')
def save_current_draft():
    payload = _json_body()
    week_start = week_start_for()
    existed = WeeklyReport.query.filter_by(week_start=week_start, user_id=g.learning_user_id).first() is not None
    report = save_draft(g.learning_user_id, payload, payload.get('draft_revision'))
    return jsonify(serialize_report(report)), 200 if existed else 201


@learning_bp.route('/reports/current/submit', methods=['POST'])
@learning_surface_required('user')
def submit_current_report():
    payload = _json_body()
    report = submit_report(g.learning_user_id, payload.get('draft_revision'))
    return jsonify(serialize_report(report))


@learning_bp.route('/reports/history', methods=['GET'])
@learning_surface_required('user')
def report_history():
    return jsonify({'items': list_history(
        g.learning_user_id,
        from_week=_week_query('from_week'),
        to_week=_week_query('to_week'),
    )})


@learning_bp.route('/reports/submission-history', methods=['GET'])
@learning_surface_required('user')
def report_submission_history():
    return jsonify(_serialize_stats_dates(submission_history(g.learning_user_id)))


@learning_bp.route('/reports/<int:report_id>', methods=['GET'])
@learning_surface_required('user')
def report_detail(report_id):
    return jsonify(serialize_report(get_report(g.learning_user_id, report_id)))


@learning_bp.route('/reports/<int:report_id>/draft', methods=['PUT'])
@learning_surface_required('user')
def save_historical_draft(report_id):
    payload = _json_body()
    return jsonify(serialize_report(save_draft(
        g.learning_user_id, payload, payload.get('draft_revision'), report_id=report_id,
    )))


@learning_bp.route('/reports/<int:report_id>/submit', methods=['POST'])
@learning_surface_required('user')
def submit_historical_report(report_id):
    payload = _json_body()
    return jsonify(serialize_report(submit_report(
        g.learning_user_id, payload.get('draft_revision'), report_id=report_id,
    )))


@learning_bp.route('/admin/users', methods=['GET'])
@learning_roles_required('hr', 'boss', login_surface='admin')
def admin_users():
    return jsonify(list_users(
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 50),
    ))


@learning_bp.route('/admin/users/<int:user_id>/role', methods=['PATCH'])
@learning_roles_required('hr', 'boss', login_surface='admin')
def admin_change_role(user_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or 'role' not in payload:
        raise LearningValidationError('role is required')
    return jsonify(change_role(
        target_user_id=user_id,
        new_role=payload['role'],
        operator_user_id=g.learning_user_id,
    ))


@learning_bp.route('/admin/role-change-logs', methods=['GET'])
@learning_roles_required('hr', 'boss', login_surface='admin')
def admin_role_change_logs():
    return jsonify(list_role_change_logs(
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 50),
    ))


@learning_bp.route('/admin/weekly-stats', methods=['GET'])
@learning_surface_required('admin')
def admin_weekly_stats():
    week_start = _week_query('week_start')
    if week_start is None:
        week_start = week_start_for()
    return jsonify(_serialize_stats_dates(weekly_stats(week_start)))


@learning_bp.route('/admin/export/recent-week', methods=['GET'])
@learning_surface_required('admin')
def admin_export_recent_week():
    payload, week_start = recent_week_csv()
    return Response(
        payload,
        content_type='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename=intern_rpa_learning_{week_start:%Y%m%d}.csv',
        },
    )


@learning_bp.route('/admin/users/<int:user_id>/trend', methods=['GET'])
@learning_surface_required('admin')
def admin_user_trend(user_id):
    return jsonify(_serialize_stats_dates(user_trend(
        user_id,
        _week_query('from_week'),
        _week_query('to_week'),
    )))


@learning_bp.route('/admin/users/<int:user_id>/history', methods=['GET'])
@learning_surface_required('admin')
def admin_user_history(user_id):
    return jsonify(_serialize_stats_dates(user_history(user_id)))


@learning_bp.route('/admin/reports/<int:report_id>/return', methods=['POST'])
@learning_roles_required('hr', 'boss', login_surface='admin')
def admin_return_report(report_id):
    payload = _json_body()
    return jsonify(serialize_report(return_report(
        report_id,
        g.learning_user_id,
        payload.get('reason'),
        payload.get('edit_deadline'),
    )))
