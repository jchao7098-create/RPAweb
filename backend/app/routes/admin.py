import csv
import io

from flask import Blueprint, g, request, jsonify, Response
from .. import db
from app.models.models import Project, ProjectLog, User, Requirement, MaintenanceRecord, Asset
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from app.learning.auth import decode_learning_token, learning_login_fields
from app.learning.errors import LearningError
from app.learning.roles import get_role
from app.passwords import verify_password
from app.departments import normalize_department
from app.platform_exports import all_intern_learning_csv, build_full_platform_archive
from app.project_status import (
    display_status_for_project,
    normalize_project_progress,
    project_status_for_progress,
    project_status_for_log_update,
    project_status_for_update,
)

from .serializers import (
    serialize_asset,
    serialize_maintenance_record,
    serialize_project,
    serialize_requirement,
)


admin_bp = Blueprint('admin', __name__)
_COMPANY_PROGRESS_ADMIN_ENDPOINTS = {
    'admin.update_progress',
    'admin.update_asset_progress',
}
_COMPANY_PROGRESS_ADMIN_ROLES = {'hr', 'boss'}


@admin_bp.before_request
def require_user_management_session():
    """Protect user-side management routes and all full-platform export routes.

    The original /admin routes remain available for backward compatibility.  The same
    blueprint is also registered as /user/manage.  User-side routes require a signed
    user token; individual routes decide whether records are owner-scoped or shared
    across the workbench. Export routes require the matching signed login token on
    both surfaces.
    """
    is_user_management = request.blueprint == 'user_management'
    is_admin_export = (
        request.blueprint == 'admin'
        and request.path.startswith('/admin/export/')
    )
    is_admin_progress_update = request.endpoint in _COMPANY_PROGRESS_ADMIN_ENDPOINTS
    if request.method == 'OPTIONS' or not (
        is_user_management or is_admin_export or is_admin_progress_update
    ):
        return None

    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token:
        message = '请先登录用户工作台' if is_user_management else '请先登录管理员端'
        return jsonify({'message': message}), 401
    try:
        user_id, login_surface = decode_learning_token(token)
    except LearningError as error:
        return jsonify({'message': error.message}), error.status_code
    expected_surface = 'user' if is_user_management else 'admin'
    if login_surface != expected_surface:
        message = '请使用用户端账号登录' if is_user_management else '请使用管理员端账号登录'
        return jsonify({'message': message}), 403
    if db.session.get(User, user_id) is None:
        return jsonify({'message': '用户不存在'}), 401

    role = get_role(user_id)
    if is_admin_progress_update and role not in _COMPANY_PROGRESS_ADMIN_ROLES:
        return jsonify({'message': '仅管理员可以修改全公司开发进度'}), 403

    if is_user_management:
        g.management_user_id = user_id
        g.management_can_edit_all = role in _COMPANY_PROGRESS_ADMIN_ROLES
    elif is_admin_progress_update:
        g.admin_progress_user_id = user_id
    return None


def _management_user_id():
    return getattr(g, 'management_user_id', None)


def _management_can_edit_all():
    return bool(getattr(g, 'management_can_edit_all', False))


def _progress_actor_user_id():
    return (
        getattr(g, 'management_user_id', None)
        or getattr(g, 'admin_progress_user_id', None)
    )


def _owned_or_not_found(query, model_id):
    """Resolve an entity from a query whose caller has already applied its scope."""
    item = query.filter_by(id=model_id).first()
    return item



@admin_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204  # CORS 预检请求

    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not password:
        return jsonify({'message': '密码不能为空'}), 400

    if username:
        user = User.query.filter_by(username=username).first()
    elif email:
        user = User.query.filter_by(email=email).first()
    else:
        return jsonify({'message': '用户名或邮箱必须提供一个'}), 400

    if not user or not verify_password(user.password, password):
        return jsonify({'message': '账号或密码错误'}), 401

    payload = {'message': '登录成功', 'admin_id': user.id}
    payload.update(learning_login_fields(user.id, 'admin'))
    return jsonify(payload), 200

@admin_bp.route('/requirements', methods=['GET'])
def get_requirements():
    try:
        query = db.session.query(Requirement)
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(Requirement.user_id == management_user_id)
        requirements = query.order_by(Requirement.created_at.desc()).all()
        # 管理端口径：比公开接口多 description 与 credentials（账号/密码）
        return jsonify([serialize_requirement(r, include_admin_fields=True) for r in requirements])

    except Exception as e:
        print(f"Error while fetching requirements: {str(e)}")
        return jsonify({'error': '内部服务器错误', 'details': str(e)}), 500


@admin_bp.route('/requirements/approve', methods=['POST'])
def approve_requirement():
    try:
        data = request.get_json(silent=True) or {}
        requirement_id = data.get('id')
        if not isinstance(requirement_id, int) or isinstance(requirement_id, bool):
            return jsonify({'error': '需求编号无效'}), 400

        query = Requirement.query
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(Requirement.user_id == management_user_id)
        requirement = _owned_or_not_found(query, requirement_id)
        if not requirement:
            return jsonify({'error': '需求不存在'}), 404
        if requirement.status != '待审核':
            return jsonify({'error': '只能审核待审核需求'}), 409

        requirement.status = '已通过'
        requirement.updated_at = datetime.utcnow()

        new_project = Project(
            name=requirement.title,
            description=requirement.description,
            created_by=requirement.user_id,
            created_at=datetime.utcnow(),
            status=project_status_for_progress(0),
            progress=0.0
        )
        db.session.add(new_project)
        db.session.commit()

        return jsonify({'message': '需求已通过，并创建了新项目'}), 200

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/requirements/reject', methods=['POST'])
def reject_requirement():
    try:
        data = request.get_json(silent=True) or {}
        requirement_id = data.get('id')
        reject_reason = data.get('reason')
        if not isinstance(requirement_id, int) or isinstance(requirement_id, bool):
            return jsonify({'error': '需求编号无效'}), 400
        
        query = Requirement.query
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(Requirement.user_id == management_user_id)
        requirement = _owned_or_not_found(query, requirement_id)
        if not requirement:
            return jsonify({'error': '需求不存在'}), 404
        if requirement.status != '待审核':
            return jsonify({'error': '只能审核待审核需求'}), 409
        
        requirement.status = '已拒绝'
        requirement.updated_at = datetime.utcnow()
        # 已知限制：requirements 表没有 reject_reason 列，下面这行赋值不会入库，
        # 拒绝理由目前不持久化。要保存需先在 MySQL 加列并同步 models.Requirement。
        requirement.reject_reason = reject_reason
        db.session.commit()
        
        return jsonify({'message': '需求已拒绝'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/get_projects', methods=['GET'])
def get_projects_with_logs():
    try:
        # 预加载 logs 与开发者，固定 2 条 SQL，避免逐项目、逐日志的 N+1 查询
        query = Project.query
        management_user_id = _management_user_id()
        read_all = (
            management_user_id is not None
            and request.args.get('scope') == 'all'
        )
        if management_user_id is not None and not read_all:
            query = query.filter(Project.created_by == management_user_id)
        projects = (
            query
            .options(selectinload(Project.logs).joinedload(ProjectLog.developer))
            .order_by(Project.created_at.desc())
            .all()
        )
        data = []
        for project in projects:
            item = serialize_project(project)
            if management_user_id is not None:
                is_owned = project.created_by == management_user_id
                item['is_owned'] = is_owned
                item['can_edit'] = is_owned or _management_can_edit_all()
            data.append(item)
        return jsonify(success=True, data=data)

    except Exception as e:
        return jsonify(success=False, message=str(e))


# 更新开发进度
@admin_bp.route('/update_progress', methods=['POST'])
def update_progress():
    try:
        data = request.get_json()

        # 必要的验证
        if not data or 'project_id' not in data or 'progress' not in data:
            return jsonify({"success": False, "message": "缺少必要参数"}), 400
        
        # 获取项目
        management_user_id = _management_user_id()
        project = Project.query.filter_by(id=data['project_id']).first()
        if not project:
            return jsonify({"success": False, "message": "项目不存在"}), 404
        if (
            management_user_id is not None
            and not _management_can_edit_all()
            and project.created_by != management_user_id
        ):
            return jsonify({
                "success": False,
                "message": "普通用户只能修改自己上传的 RPA 项目",
            }), 403
        
        # 进度条与生命周期状态彼此独立；状态以最新项目日志为准。
        current_status = display_status_for_project(project)
        progress = normalize_project_progress(data['progress'])
        requested_status = data.get('status')
        resolved_status = project_status_for_log_update(
            current_status,
            requested_status,
        )
        project.progress = progress
        project.status = resolved_status
        
        # 备注更新或显式状态选择都必须留下日志，保证后续展示有权威来源。
        remark = str(data.get('remark') or '').strip()
        has_explicit_status = requested_status not in (None, '', 'auto')
        if remark or has_explicit_status:
            new_log = ProjectLog(
                developer_id=_progress_actor_user_id(),
                status=resolved_status,
                remark=remark or '状态更新',
                project_id=project.id,
                log_time=datetime.utcnow()
            )
            db.session.add(new_log)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "进度更新成功",
            "progress": project.progress,
            "status": project.status,
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": str(e),
        }), 400
        
    except Exception as e:
        db.session.rollback()
        print("Error updating progress:", str(e))  # 详细的错误日志
        return jsonify({
            "success": False,
            "message": f"更新进度失败: {str(e)}"
        }), 500



# 获取维护记录列表（带分页）
@admin_bp.route('/maintenance', methods=['GET'])
def get_maintenance_records():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # 基础查询
        query = MaintenanceRecord.query
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(or_(
                MaintenanceRecord.maintainer_id == management_user_id,
                MaintenanceRecord.requester_id == management_user_id,
            ))
        
        # 排序（按维护日期降序）
        query = query.order_by(MaintenanceRecord.maintenance_date.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        records = pagination.items
        
        result = {
            'items': [serialize_maintenance_record(record) for record in records],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }

        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({'error': '获取维护记录失败'}), 500

# 获取维护统计信息

# 获取单条维护记录详情
@admin_bp.route('/maintenance/<int:record_id>', methods=['GET'])
def get_maintenance_record(record_id):
    try:
        query = MaintenanceRecord.query
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(or_(
                MaintenanceRecord.maintainer_id == management_user_id,
                MaintenanceRecord.requester_id == management_user_id,
            ))
        record = query.filter_by(id=record_id).first()
        if not record:
            return jsonify({'error': '维护记录不存在'}), 404

        return jsonify(serialize_maintenance_record(record)), 200
        
    except Exception as e:
        # Blueprint 对象没有 logger 属性，此前写 admin_bp.logger 会在异常处理时再抛
        # AttributeError 把原始错误吞掉，统一用 print 与本文件其他错误输出保持一致
        print(f"获取维护记录详情失败: {str(e)}")
        return jsonify({'error': '获取维护记录详情失败'}), 500

# 删除维护记录
@admin_bp.route('/maintenance/<int:record_id>', methods=['DELETE'])
def delete_maintenance_record(record_id):
    try:
        query = MaintenanceRecord.query
        management_user_id = _management_user_id()
        if management_user_id is not None:
            query = query.filter(or_(
                MaintenanceRecord.maintainer_id == management_user_id,
                MaintenanceRecord.requester_id == management_user_id,
            ))
        record = query.filter_by(id=record_id).first()
        if not record:
            return jsonify({'error': '维护记录不存在'}), 404
        db.session.delete(record)
        db.session.commit()
        
        return jsonify({'message': '维护记录删除成功'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"删除维护记录失败: {str(e)}")
        return jsonify({'error': '删除维护记录失败'}), 500

# 创建维护记录
@admin_bp.route('/maintenance', methods=['POST'])
def create_maintenance_record():
    try:
        data = request.get_json(silent=True) or {}
        management_user_id = _management_user_id()
        
        # 验证必要字段
        required_fields = ['project_id', 'project_name', 'maintainer_id', 
                          'maintainer_name', 'requester_id', 'requester_name',
                          'maintenance_details']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'缺少必要字段: {field}'}), 400
        if management_user_id is not None:
            data['maintainer_id'] = management_user_id
        
        # 创建新记录
        new_record = MaintenanceRecord(
            project_id=data['project_id'],
            project_name=data['project_name'],
            maintainer_id=data['maintainer_id'],
            maintainer_name=data['maintainer_name'],
            requester_id=data['requester_id'],
            requester_name=data['requester_name'],
            maintenance_details=data['maintenance_details'],
            maintenance_date=data.get('maintenance_date') or datetime.utcnow()
        )
        
        db.session.add(new_record)
        db.session.commit()
        
        return jsonify({
            'message': '维护记录创建成功',
            'id': new_record.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"创建维护记录失败: {str(e)}")
        return jsonify({'error': '创建维护记录失败'}), 500





















# ===== 员工代码资产审核（Skill 文件 / Python 插件）=====

@admin_bp.route('/assets', methods=['GET'])
def get_assets():
    """管理员查看所有资产提交，支持按 asset_type / status 筛选"""
    asset_type = request.args.get('asset_type')
    status = request.args.get('status')
    query = Asset.query
    management_user_id = _management_user_id()
    read_all = (
        management_user_id is not None
        and request.args.get('scope') == 'all'
    )
    if management_user_id is not None and not read_all:
        query = query.filter(Asset.user_id == management_user_id)
    elif read_all:
        # 用户工作台的“全量开发进度”只需要已通过资产的公开进度字段；
        # 待审核/拒绝理由仍属于提交人与审核端，不在这里向其他用户披露。
        query = query.filter(Asset.status == '已通过')
    if asset_type:
        query = query.filter_by(asset_type=asset_type)
    if status:
        query = query.filter_by(status=status)
    assets = query.order_by(Asset.created_at.desc()).all()
    data = []
    for asset in assets:
        item = serialize_asset(
            asset,
            include_reject_reason=not read_all,
            include_type=True,
        )
        if management_user_id is not None:
            is_owned = asset.user_id == management_user_id
            item['is_owned'] = is_owned
            item['can_edit'] = is_owned or _management_can_edit_all()
        data.append(item)
    return jsonify({'data': data})


@admin_bp.route('/assets/approve', methods=['POST', 'OPTIONS'])
def approve_asset():
    """通过资产审核"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    asset_id = data.get('id')
    query = Asset.query
    management_user_id = _management_user_id()
    if management_user_id is not None:
        query = query.filter(Asset.user_id == management_user_id)
    asset = query.filter_by(id=asset_id).first()
    if not asset:
        return jsonify({'error': '资产不存在'}), 404
    if asset.status != '待审核':
        return jsonify({'error': '只能审核待审核资产'}), 409
    asset.status = '已通过'
    asset.reject_reason = None
    db.session.commit()
    return jsonify({'message': '已通过'})


@admin_bp.route('/assets/reject', methods=['POST', 'OPTIONS'])
def reject_asset():
    """拒绝资产"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    asset_id = data.get('id')
    reason = (data.get('reason') or '').strip()
    query = Asset.query
    management_user_id = _management_user_id()
    if management_user_id is not None:
        query = query.filter(Asset.user_id == management_user_id)
    asset = query.filter_by(id=asset_id).first()
    if not asset:
        return jsonify({'error': '资产不存在'}), 404
    if asset.status != '待审核':
        return jsonify({'error': '只能审核待审核资产'}), 409
    asset.status = '已拒绝'
    asset.reject_reason = reason or None
    db.session.commit()
    return jsonify({'message': '已拒绝'})


@admin_bp.route('/assets/progress', methods=['POST', 'OPTIONS'])
def update_asset_progress():
    """更新已审核 Skill / Python 插件的进度和生命周期状态。"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    asset_id = data.get('id')
    if 'progress' not in data:
        return jsonify({'error': '缺少进度'}), 400

    asset = Asset.query.filter_by(id=asset_id).first()
    if not asset:
        return jsonify({'error': '资产不存在'}), 404
    management_user_id = _management_user_id()
    if (
        management_user_id is not None
        and not _management_can_edit_all()
        and asset.user_id != management_user_id
    ):
        return jsonify({
            'error': '普通用户只能修改自己上传的 Skill 或 Python 文件',
        }), 403
    if asset.status != '已通过':
        return jsonify({'error': '资产必须先审核通过，才能管理开发进度'}), 409

    try:
        progress = normalize_project_progress(data['progress'])
        lifecycle_status = project_status_for_update(progress, data.get('lifecycle_status'))
        asset.progress = progress
        asset.lifecycle_status = lifecycle_status
        db.session.commit()
        return jsonify({
            'message': '进度更新成功',
            'id': asset.id,
            'progress': asset.progress,
            'lifecycle_status': asset.lifecycle_status,
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ===== 数据导出（CSV）=====

def _csv_response(rows, filename):
    """rows（二维列表）→ 带 UTF-8 BOM 的 CSV 附件响应，Excel 直接打开不乱码。"""
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response(
        ('\ufeff' + buf.getvalue()).encode('utf-8'),  # BOM 让 Excel 按 UTF-8 识别
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@admin_bp.route('/export/weekly_stats', methods=['GET'])
def export_weekly_stats():
    """导出全平台近 7 天数据统计。

    时间口径说明：主库（需求/项目/日志/维护）created_at 存的是 utcnow，
    资产库存的是本地时间，因此各自用对应基准取"近 7 天"，边界差异约 8 小时属已知现象。
    """
    try:
        since_utc = datetime.utcnow() - timedelta(days=7)
        since_local = datetime.now() - timedelta(days=7)
        req_query = Requirement.query.filter(Requirement.created_at >= since_utc)
        project_query = Project.query.filter(Project.created_at >= since_utc)
        log_query = ProjectLog.query.filter(ProjectLog.log_time >= since_utc)
        maintenance_query = MaintenanceRecord.query.filter(MaintenanceRecord.created_at >= since_utc)
        user_query = User.query.filter(User.created_at >= since_utc)
        skill_query = Asset.query.filter(Asset.asset_type == 'skill', Asset.created_at >= since_local)
        python_query = Asset.query.filter(Asset.asset_type == 'python_plugin', Asset.created_at >= since_local)
        approved_asset_query = Asset.query.filter(Asset.status == '已通过', Asset.created_at >= since_local)
        rows = [
            ['指标', '数量'],
            ['统计生成时间', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['统计范围', '全平台近 7 天'],
            ['新增需求（RPA 程序）', req_query.count()],
            ['其中：待审核', req_query.filter(Requirement.status == '待审核').count()],
            ['其中：已通过', req_query.filter(Requirement.status == '已通过').count()],
            ['其中：已拒绝', req_query.filter(Requirement.status == '已拒绝').count()],
            ['新增开发项目', project_query.count()],
            ['开发日志条数', log_query.count()],
            ['维护记录条数', maintenance_query.count()],
            ['新增注册用户', user_query.count()],
            ['新增 Skill 提交', skill_query.count()],
            ['新增 Python 插件提交', python_query.count()],
            ['资产审核通过数', approved_asset_query.count()],
        ]
        return _csv_response(rows, f"weekly_stats_{datetime.now().strftime('%Y%m%d')}.csv")
    except Exception as e:
        print('导出周统计失败：', str(e))
        return jsonify({'error': '导出失败'}), 500


@admin_bp.route('/export/upload_names', methods=['GET'])
def export_upload_names():
    """导出全平台上传记录：RPA 程序（需求）+ Skill 文件 + Python 插件。"""
    try:
        rows = [['类型', '名称', '文件名', '部门', '提交人', '状态', '提交时间']]

        requirement_query = Requirement.query
        asset_query = Asset.query

        for r in requirement_query.order_by(Requirement.created_at.desc()).all():
            rows.append([
                'RPA 程序', r.title, '', normalize_department(r.department), r.requester or '',
                r.status or '', r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
            ])

        type_label = {'skill': 'Skill 文件', 'python_plugin': 'Python 插件'}
        for a in asset_query.order_by(Asset.created_at.desc()).all():
            rows.append([
                type_label.get(a.asset_type, a.asset_type), a.name, a.file_name or '',
                normalize_department(a.department), a.submitter or '', a.status or '',
                a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else '',
            ])

        return _csv_response(rows, f"upload_names_{datetime.now().strftime('%Y%m%d')}.csv")
    except Exception as e:
        print('导出名称清单失败：', str(e))
        return jsonify({'error': '导出失败'}), 500


@admin_bp.route('/export/intern_learning', methods=['GET'])
def export_intern_learning():
    """导出全平台实习生全部历史 RPA 学习情况。"""
    try:
        payload = all_intern_learning_csv()
        return Response(
            payload,
            content_type='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': (
                    f'attachment; filename=intern_rpa_learning_all_{datetime.now():%Y%m%d}.csv'
                ),
            },
        )
    except Exception as e:
        print('导出实习生学习情况失败：', str(e))
        return jsonify({'error': '导出失败'}), 500


@admin_bp.route('/export/full_archive', methods=['GET'])
def export_full_archive():
    """导出全平台完整数据 ZIP；敏感认证信息明确排除。"""
    try:
        payload = build_full_platform_archive()
        return Response(
            payload,
            content_type='application/zip',
            headers={
                'Content-Disposition': (
                    f'attachment; filename=aitools_full_export_{datetime.now():%Y%m%d}.zip'
                ),
            },
        )
    except Exception as e:
        print('导出全平台数据包失败：', str(e))
        return jsonify({'error': '导出失败'}), 500


@admin_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'admin sussess'})
