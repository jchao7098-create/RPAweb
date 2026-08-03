from flask import Blueprint, current_app, request, jsonify
from werkzeug.utils import secure_filename
from .. import db
from app.models.models import Project, ProjectLog, MaintenanceItem, MaintenanceLog, User, Requirement, MaintenanceRecord, Asset
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload
from app.learning.auth import decode_learning_token, learning_login_fields
from app.learning.errors import LearningError
from app.learning.roles import confirm_initial_employment_type
from app.passwords import (
    PasswordResetDeliveryError,
    PasswordResetError,
    build_password_reset_url,
    hash_password,
    issue_password_reset_token,
    load_password_reset_user,
    password_reset_delivery_configured,
    send_password_reset_email,
    verify_password,
)
from app.departments import normalize_department

from .serializers import serialize_asset, serialize_project, serialize_user_requirement


user_bp = Blueprint('user', __name__)


def _authenticated_user_id():
    """Resolve a signed user-workbench session for owner-scoped RPA routes."""
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return None, (jsonify({'message': '请先登录用户工作台'}), 401)
    try:
        user_id, login_surface = decode_learning_token(token)
    except LearningError as error:
        return None, (jsonify({'message': error.message}), error.status_code)
    if login_surface != 'user':
        return None, (jsonify({'message': '请使用用户端账号登录'}), 403)
    if db.session.get(User, user_id) is None:
        return None, (jsonify({'message': '用户不存在'}), 401)
    return user_id, None


def _validate_claimed_user_id(value, authenticated_user_id):
    """Reject forged client-side ids while keeping old clients compatible."""
    if value in (None, ''):
        return None
    try:
        claimed_user_id = int(value)
    except (TypeError, ValueError):
        return jsonify({'message': 'user_id 必须为整数'}), 400
    if claimed_user_id != authenticated_user_id:
        return jsonify({'message': '无权访问其他用户的数据'}), 403
    return None


@user_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204  # CORS 预检请求

    data = request.get_json(silent=True) or {}
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

    try:
        employment_type = confirm_initial_employment_type(
            user.id, data.get('employment_type')
        )
    except LearningError as error:
        message = error.message
        if error.status_code == 422:
            message = '请选择有效职位'
        elif error.status_code == 409:
            message = '职位已固定，如需修改请联系管理员'
        return jsonify({'message': message}), error.status_code

    payload = {
        'message': '登录成功',
        'user_id': user.id,
        'employment_type': employment_type,
    }
    payload.update(learning_login_fields(user.id, 'user'))
    return jsonify(payload), 200


@user_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return '', 204  # CORS 预检请求

    data = request.json or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'message': '用户名、邮箱和密码均不能为空'}), 400

    if len(username) > 100 or len(email) > 100:
        return jsonify({'message': '用户名或邮箱过长'}), 400

    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'message': '邮箱格式不正确'}), 400

    if len(password) < 6:
        return jsonify({'message': '密码长度至少 6 位'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': '该用户名已被注册'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'message': '该邮箱已被注册'}), 409

    try:
        new_user = User(username=username, email=email, password=hash_password(password))
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print('注册失败：', str(e))
        return jsonify({'message': '服务器错误，注册失败'}), 500

    return jsonify({'message': '注册成功', 'user_id': new_user.id}), 201


@user_bp.route('/password-reset/request', methods=['POST', 'OPTIONS'])
def request_password_reset():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    audience = (data.get('audience') or 'user').strip().lower()

    if not email:
        return jsonify({'message': '请输入注册邮箱'}), 400
    if len(email) > 100 or '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'message': '邮箱格式不正确'}), 400
    if audience not in ('user', 'admin'):
        return jsonify({'message': '无效的登录入口'}), 400
    if not password_reset_delivery_configured():
        return jsonify({'message': '密码找回邮件服务尚未配置，请联系管理员'}), 503

    # 不论邮箱是否存在都返回相同文案，避免通过接口枚举系统账号。
    response_payload = {
        'message': '如果该邮箱已注册，重置邮件会在几分钟内发送',
    }
    user = User.query.filter(func.lower(User.email) == email.lower()).first()
    if not user:
        return jsonify(response_payload), 200

    token = issue_password_reset_token(user, audience)
    reset_url = build_password_reset_url(token, audience)
    if current_app.config.get('PASSWORD_RESET_EXPOSE_TOKEN'):
        response_payload.update({'reset_token': token, 'reset_url': reset_url})
        return jsonify(response_payload), 200

    try:
        send_password_reset_email(user, reset_url)
    except PasswordResetDeliveryError:
        current_app.logger.exception('Password reset email delivery failed')
        # 对外仍返回与未知邮箱相同的结果，避免借 SMTP 故障枚举已注册账号；
        # 具体失败原因只写服务端日志，由管理员排查。
        return jsonify(response_payload), 200
    return jsonify(response_payload), 200


@user_bp.route('/password-reset/confirm', methods=['POST', 'OPTIONS'])
def confirm_password_reset():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    token = data.get('token') or ''
    new_password = data.get('password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not token:
        return jsonify({'message': '缺少密码重置凭证'}), 400
    if len(new_password) < 6:
        return jsonify({'message': '密码长度至少 6 位'}), 400
    if new_password != confirm_password:
        return jsonify({'message': '两次输入的密码不一致'}), 400

    try:
        user, audience = load_password_reset_user(token)
    except PasswordResetError as error:
        return jsonify({'message': str(error)}), 400

    try:
        user.password = hash_password(new_password)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Password reset failed')
        return jsonify({'message': '密码修改失败，请稍后重试'}), 500

    return jsonify({
        'message': '密码已重置，请使用新密码登录',
        'username': user.username,
        'email': user.email,
        'audience': audience,
    }), 200

@user_bp.route('/submit_requirement', methods=['POST'])
def submit_requirement():
    """
    用户提交开发需求，字段校验 + 错误信息反馈更清晰
    """
    try:
        authenticated_user_id, auth_error = _authenticated_user_id()
        if auth_error:
            return auth_error

        data = request.form
        claimed_user_error = _validate_claimed_user_id(
            data.get('user_id'),
            authenticated_user_id,
        )
        if claimed_user_error:
            return claimed_user_error

        required_fields = ['title', 'description', 'department', 'requester', 'priority', 'feedback_time', 'expected_finish_time']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            print(missing_fields)
            return jsonify({'error': f"以下字段不能为空: {', '.join(missing_fields)}"}), 400

        # 获取字段
        title = data.get('title')
        description = data.get('description')
        department = normalize_department(data.get('department'), default='')
        requester = data.get('requester')
        priority = data.get('priority')
        platform = data.get('platform')
        operation_link = data.get('operation_link')
        account = data.get('account')
        password = data.get('password')

        # 时间字段格式校验（两个字段同一格式，前端也做了预校验，出错时统一提示即可）
        try:
            feedback_time = datetime.strptime(data.get('feedback_time'), '%Y-%m-%d %H:%M:%S')
            expected_finish_time = datetime.strptime(data.get('expected_finish_time'), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'error': '时间格式错误，应为 YYYY-MM-DD HH:mm:ss'}), 400

        # 创建需求实例
        new_requirement = Requirement(
            user_id=authenticated_user_id,
            title=title,
            description=description,
            department=normalize_department(department, default=''),
            requester=requester,
            feedback_time=feedback_time,
            priority=priority,
            expected_finish_time=expected_finish_time,
            platform=platform,
            operation_link=operation_link,
            account=account,
            password=password,
            status='待审核',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 附件处理（保存路径或名称）
        attachments = []
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(f'./uploads/{filename}')  # 可自定义路径
                attachments.append(filename)

        new_requirement.attachments = attachments

        # 提交数据库
        db.session.add(new_requirement)
        db.session.commit()
        return jsonify({'message': '需求提交成功'}), 201

    except Exception as e:
        db.session.rollback()
        print(str(e))
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@user_bp.route('/get_my_requirements', methods=['GET'])
def get_my_requirements():
    """
    获取当前用户提交的所有项目需求（按创建时间倒序排列）
    参数：user_id（通过 URL 参数传递）
    """
    authenticated_user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    claimed_user_error = _validate_claimed_user_id(
        request.args.get('user_id'),
        authenticated_user_id,
    )
    if claimed_user_error:
        return claimed_user_error
    try:
        requirements = (
            Requirement.query
            .filter_by(user_id=authenticated_user_id)
            .order_by(Requirement.created_at.desc())
            .all()
        )

        return jsonify({'data': [serialize_user_requirement(r) for r in requirements]})
    
    except Exception as e:
        # 捕获错误并打印以便调试
        print('查询失败：', str(e))
        return jsonify({'error': '服务器内部错误'}), 500


@user_bp.route('/requirements/<int:requirement_id>', methods=['PATCH', 'OPTIONS'])
def update_my_requirement(requirement_id):
    """修改本人尚未通过的 RPA 需求；保存后重新进入待审核。"""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({'message': 'user_id 必须为整数'}), 400

    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return jsonify({'message': '请先登录用户工作台'}), 401
    try:
        token_user_id, login_surface = decode_learning_token(token)
    except LearningError as error:
        return jsonify({'message': error.message}), error.status_code
    if login_surface != 'user' or token_user_id != user_id:
        return jsonify({'message': '无权修改该需求'}), 403

    requirement = Requirement.query.filter_by(
        id=requirement_id,
        user_id=user_id,
    ).first()
    if not requirement:
        return jsonify({'message': '需求不存在或无权修改'}), 404
    if requirement.status not in ('待审核', '已拒绝'):
        return jsonify({'message': '已通过或已取消的需求不能修改'}), 409

    required_fields = (
        'title',
        'description',
        'department',
        'requester',
        'priority',
        'feedback_time',
        'expected_finish_time',
    )
    missing = [
        field for field in required_fields
        if not str(data.get(field) or '').strip()
    ]
    if missing:
        return jsonify({'message': f"以下字段不能为空: {', '.join(missing)}"}), 400

    priority = str(data.get('priority')).strip()
    if priority not in ('高', '中', '低'):
        return jsonify({'message': '紧急程度必须为高、中或低'}), 400

    title = str(data.get('title')).strip()
    department = normalize_department(data.get('department'), default='')
    requester = str(data.get('requester')).strip()
    description = str(data.get('description')).strip()
    if len(title) > 255 or len(department) > 255 or len(requester) > 255:
        return jsonify({'message': '标题、部门或需求人姓名过长'}), 400

    try:
        feedback_time = datetime.strptime(
            str(data.get('feedback_time')).strip(),
            '%Y-%m-%d %H:%M:%S',
        )
        expected_finish_time = datetime.strptime(
            str(data.get('expected_finish_time')).strip(),
            '%Y-%m-%d %H:%M:%S',
        )
    except ValueError:
        return jsonify({'message': '时间格式错误，应为 YYYY-MM-DD HH:mm:ss'}), 400

    requirement.title = title
    requirement.description = description
    requirement.department = department
    requirement.requester = requester
    requirement.priority = priority
    requirement.feedback_time = feedback_time
    requirement.expected_finish_time = expected_finish_time
    requirement.platform = str(data.get('platform') or '').strip() or None
    requirement.operation_link = str(data.get('operation_link') or '').strip() or None
    requirement.account = str(data.get('account') or '').strip() or None
    new_password = str(data.get('password') or '')
    if new_password:
        requirement.password = new_password
    requirement.status = '待审核'
    requirement.updated_at = datetime.now()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Requirement update failed')
        return jsonify({'message': '需求修改失败，请稍后重试'}), 500

    return jsonify({
        'message': '需求已更新，等待重新审核',
        'data': serialize_user_requirement(requirement),
    })

# 获取用户参与的项目（通过 ProjectLog）
@user_bp.route('/get_my_projects', methods=['GET'])
def get_my_projects():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(success=False, message='缺少 user_id 参数')

    # 查询该用户创建的所有项目；预加载 logs 与开发者，固定 2 条 SQL 避免 N+1
    projects = (
        Project.query
        .filter_by(created_by=user_id)
        .options(selectinload(Project.logs).joinedload(ProjectLog.developer))
        .order_by(Project.created_at.desc())
        .all()
    )
    return jsonify(success=True, data=[serialize_project(p) for p in projects])





# 获取用户参与的所有维护任务（通过 MaintenanceLog）
@user_bp.route('/get_my_maintenance_tasks', methods=['GET'])
def get_my_maintenance_tasks():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'code': 400, 'msg': '缺少 user_id'}), 400

    try:
        logs = MaintenanceLog.query.filter_by(operator_id=user_id).all()
        maintenance_ids = list(set(log.maintenance_id for log in logs))

        tasks = MaintenanceItem.query.filter(MaintenanceItem.id.in_(maintenance_ids)).all()
        data = []
        for task in tasks:
            data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'progress': task.progress,
                'status': task.status,
                'created_at': task.created_at
            })
        return jsonify({'code': 200, 'msg': 'success', 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'服务异常: {str(e)}'})





@user_bp.route('/maintenance', methods=['GET'])
def get_my_maintenance():
    """
    获取当前用户的所有维护记录（按创建时间倒序排列）
    参数：user_id（通过URL参数传递）
    可选参数：page（页码），per_page（每页数量）
    """
    # 获取请求参数
    user_id = request.args.get('user_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 验证必要参数
    if not user_id:
        return jsonify({'error': '缺少 user_id 参数'}), 400
    
    try:
        # 查询数据库
        query = MaintenanceRecord.query.filter_by(maintainer_id=user_id)
        pagination = query.order_by(MaintenanceRecord.created_at.desc()).paginate(
            page=page, 
            per_page=per_page,
            error_out=False
        )
        
        # 格式化返回数据
        records = [{
            'id': record.id,
            'project_id': record.project_id,
            'project_name': record.project_name,
            'maintenance_date': record.maintenance_date.isoformat(),
            'requester_name': record.requester_name,
            'maintenance_details': record.maintenance_details,
            'created_at': record.created_at.isoformat()
        } for record in pagination.items]
        
        return jsonify({
            'items': records,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        })
        
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500


@user_bp.route('/get_maintenance_detail/<int:record_id>', methods=['GET'])
def get_maintenance_detail(record_id):
    """
    获取特定维护记录的详细信息
    参数：user_id（通过URL参数传递），record_id（路径参数）
    """
    user_id = request.args.get('user_id')
    
    # 验证必要参数
    if not user_id:
        return jsonify({'error': '缺少 user_id 参数'}), 400
    
    try:
        # 查询数据库
        record = MaintenanceRecord.query.filter_by(
            id=record_id,
            maintainer_id=user_id
        ).first()
        
        if not record:
            return jsonify({'error': '记录不存在或无权访问'}), 404

        # 注意：此前这里返回 record.status，但 MaintenanceRecord 模型没有该字段，
        # 每次调用都会抛 AttributeError 返回 500（前端目前未使用本接口，故一直没暴露）
        return jsonify({
            'id': record.id,
            'project_id': record.project_id,
            'project_name': record.project_name,
            'maintainer_id': record.maintainer_id,
            'maintainer_name': record.maintainer_name,
            'maintenance_date': record.maintenance_date.isoformat(),
            'requester_id': record.requester_id,
            'requester_name': record.requester_name,
            'maintenance_details': record.maintenance_details,
            'created_at': record.created_at.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500























# ===== 员工代码资产（Skill / Python 插件）=====
_ALLOWED_ASSET_TYPES = ('skill', 'python_plugin')
_ALLOWED_ASSET_EXTENSIONS = {
    'skill': ('.md', '.txt', '.json', '.yaml', '.yml', '.zip'),
    'python_plugin': ('.py', '.zip', '.whl'),
}


def _validate_asset_fields(asset_type, name, department, submitter, version, description, file_name):
    if not name or not department or not submitter or not description or not file_name:
        return '名称、部门、提交人、说明、文件名不能为空'
    if (
        len(name) > 200
        or len(department) > 100
        or len(submitter) > 100
        or len(version) > 50
        or len(description) > 2000
        or len(file_name) > 255
    ):
        return '填写内容超过长度限制'
    if not file_name.lower().endswith(_ALLOWED_ASSET_EXTENSIONS[asset_type]):
        extensions = ' / '.join(_ALLOWED_ASSET_EXTENSIONS[asset_type])
        return f'文件格式不正确，支持: {extensions}'
    return None


@user_bp.route('/assets', methods=['POST', 'OPTIONS'])
def submit_asset():
    """用户提交代码资产（当前仅登记文件名，不接收文件内容）"""
    if request.method == 'OPTIONS':
        return '', 204  # CORS 预检请求

    authenticated_user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    data = request.form or {}
    claimed_user_error = _validate_claimed_user_id(
        data.get('user_id'),
        authenticated_user_id,
    )
    if claimed_user_error:
        return claimed_user_error
    asset_type = data.get('asset_type')
    name = (data.get('name') or '').strip()
    department = (data.get('department') or '').strip()
    submitter = (data.get('submitter') or '').strip()
    version = (data.get('version') or '').strip()
    description = (data.get('description') or '').strip()
    file_name = (data.get('file_name') or '').strip()

    if asset_type not in _ALLOWED_ASSET_TYPES:
        return jsonify({'message': f'asset_type 必须为: {", ".join(_ALLOWED_ASSET_TYPES)}'}), 400
    field_error = _validate_asset_fields(
        asset_type, name, department, submitter, version, description, file_name
    )
    if field_error:
        return jsonify({'message': field_error}), 400

    try:
        asset = Asset(
            user_id=authenticated_user_id,
            asset_type=asset_type,
            name=name,
            department=normalize_department(department, default=''),
            submitter=submitter,
            version=version or None,
            description=description or None,
            file_name=file_name,
            status='待审核',
            created_at=datetime.now(),
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify({'message': '提交成功，等待管理员审核'}), 201
    except Exception as e:
        db.session.rollback()
        print('Asset 提交失败：', str(e))
        return jsonify({'message': f'服务器错误: {str(e)}'}), 500


@user_bp.route('/assets/<int:asset_id>', methods=['PATCH', 'OPTIONS'])
def update_my_asset(asset_id):
    """用户修改本人提交的 Skill/Python 信息；任何修改都必须重新审核。"""
    if request.method == 'OPTIONS':
        return '', 204

    authenticated_user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    claimed_user_error = _validate_claimed_user_id(
        data.get('user_id'),
        authenticated_user_id,
    )
    if claimed_user_error:
        return claimed_user_error

    asset = Asset.query.filter_by(
        id=asset_id,
        user_id=authenticated_user_id,
    ).first()
    if not asset:
        # 不区分“记录不存在”和“不是本人”，避免泄露其他用户的资产信息。
        return jsonify({'message': '提交记录不存在或无权修改'}), 404

    name = (data.get('name') or '').strip()
    department = normalize_department(data.get('department'), default='')
    submitter = (data.get('submitter') or '').strip()
    version = (data.get('version') or '').strip()
    description = (data.get('description') or '').strip()
    file_name = (data.get('file_name') or '').strip()
    field_error = _validate_asset_fields(
        asset.asset_type,
        name,
        department,
        submitter,
        version,
        description,
        file_name,
    )
    if field_error:
        return jsonify({'message': field_error}), 400

    try:
        asset.name = name
        asset.department = department
        asset.submitter = submitter
        asset.version = version or None
        asset.description = description
        asset.file_name = file_name
        # 已通过内容若直接覆盖会绕过审核；待审核/已拒绝也统一重新进入审核队列。
        asset.status = '待审核'
        asset.reject_reason = None
        asset.lifecycle_status = '在编'
        asset.progress = 0
        db.session.commit()
        return jsonify({
            'message': '修改已提交，等待管理员重新审核',
            'data': serialize_asset(asset, include_reject_reason=True),
        }), 200
    except Exception as e:
        db.session.rollback()
        print('Asset 修改失败：', str(e))
        return jsonify({'message': '服务器错误，修改失败'}), 500


@user_bp.route('/assets', methods=['GET'])
def get_my_assets():
    """获取当前用户提交的资产列表（按提交时间倒序）"""
    authenticated_user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    claimed_user_error = _validate_claimed_user_id(
        request.args.get('user_id'),
        authenticated_user_id,
    )
    if claimed_user_error:
        return claimed_user_error
    asset_type = request.args.get('asset_type')
    if asset_type and asset_type not in _ALLOWED_ASSET_TYPES:
        return jsonify({'error': f'asset_type 必须为: {", ".join(_ALLOWED_ASSET_TYPES)}'}), 400

    try:
        query = Asset.query.filter_by(user_id=authenticated_user_id)
        if asset_type:
            query = query.filter_by(asset_type=asset_type)
        assets = query.order_by(Asset.created_at.desc()).all()
        return jsonify({'data': [serialize_asset(a, include_reject_reason=True) for a in assets]})
    except Exception as e:
        print('Asset 查询失败：', str(e))
        return jsonify({'error': '服务器内部错误'}), 500


@user_bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'user sussess'})
