from app.departments import normalize_department
from app.project_status import display_status_for_project, project_logs_newest_first


# 路由层共享的序列化函数。
# 同一实体在多个接口返回时字段口径必须一致，改字段只改这里一处；
# 此前 public/admin/user 三处各自手写同一份 dict，字段一旦改动极易漏改。


def serialize_project(project):
    """项目（含全部开发日志）→ dict。

    注意：调用方查询时必须预加载 logs 及其 developer
    （selectinload(Project.logs).joinedload(ProjectLog.developer)），
    否则这里逐条访问关系会退化为 N+1 查询。

    status 取自日志中最新的生命周期状态（display_status_for_project），
    而非 projects.status 字段：后者只能由进度推导（在编/使用）或写入时覆盖，
    回填脚本会丢掉真正的大修/停用；日志才是权威来源。
    """
    logs = project_logs_newest_first(project.logs)
    return {
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'created_at': project.created_at.isoformat(),
        'status': display_status_for_project(project),
        'progress': project.progress,
        'logs': [{
            'id': log.id,
            'log_time': log.log_time.isoformat(),
            'developer_name': log.developer.username if log.developer else '未知开发者',
            'status': log.status,
            'remark': log.remark,
        } for log in logs],
    }


def serialize_requirement(requirement, include_admin_fields=False):
    """需求 → dict（公开口径）。

    include_admin_fields=True 时追加管理端专用字段：
    description 与 credentials（登录账号/密码），公开接口绝不能开。
    """
    fmt = '%Y-%m-%d %H:%M:%S'
    data = {
        'id': requirement.id,
        'title': requirement.title,
        'requester': requirement.requester,
        'department': normalize_department(requirement.department),
        'urgency': requirement.priority,
        'expected_time': requirement.expected_finish_time.strftime(fmt) if requirement.expected_finish_time else None,
        'feedback_time': requirement.feedback_time.strftime(fmt) if requirement.feedback_time else None,
        'platform': requirement.platform,
        'operation_link': requirement.operation_link,
        'attachment': list(requirement.attachments) if requirement.attachments else [],
        'status': requirement.status,
    }
    if include_admin_fields:
        data['description'] = requirement.description
        data['credentials'] = f"{requirement.account} / {requirement.password}"
    return data


def serialize_user_requirement(requirement):
    """需求提交人查看/修改本人记录时使用的完整口径（不返回登录密码）。"""
    fmt = '%Y-%m-%d %H:%M:%S'
    return {
        'id': requirement.id,
        'title': requirement.title,
        'description': requirement.description,
        'status': requirement.status,
        'created_at': requirement.created_at.strftime('%Y-%m-%d %H:%M') if requirement.created_at else None,
        'department': normalize_department(requirement.department),
        'requester': requirement.requester,
        'priority': requirement.priority,
        'feedback_time': requirement.feedback_time.strftime(fmt) if requirement.feedback_time else None,
        'expected_finish_time': requirement.expected_finish_time.strftime(fmt) if requirement.expected_finish_time else None,
        'platform': requirement.platform,
        'operation_link': requirement.operation_link,
        'account': requirement.account,
        'attachments': list(requirement.attachments) if requirement.attachments else [],
        'editable': requirement.status in ('待审核', '已拒绝'),
    }


def serialize_asset(asset, include_reject_reason=False, include_type=False):
    """代码资产（Skill / Python 插件）→ dict。

    三种口径：公开接口用默认参数（不含拒绝理由与类型）；
    用户"我的提交"加 include_reject_reason；管理端审核两个都开。
    """
    data = {
        'id': asset.id,
        'name': asset.name,
        'version': asset.version,
        'description': asset.description,
        'department': normalize_department(asset.department),
        'submitter': asset.submitter,
        'file_name': asset.file_name,
        'file_size': asset.file_size,
        'status': asset.status,
        'lifecycle_status': asset.lifecycle_status,
        'progress': asset.progress,
        'created_at': asset.created_at.strftime('%Y-%m-%d %H:%M') if asset.created_at else None,
    }
    if include_type:
        data['asset_type'] = asset.asset_type
    if include_reject_reason:
        data['reject_reason'] = asset.reject_reason
    return data


def serialize_maintenance_record(record):
    """维护记录 → dict（管理端列表与详情共用同一口径）。"""
    return {
        'id': record.id,
        'project_id': record.project_id,
        'project_name': record.project_name,
        'maintainer_id': record.maintainer_id,
        'maintainer_name': record.maintainer_name,
        'requester_id': record.requester_id,
        'requester_name': record.requester_name,
        'maintenance_date': record.maintenance_date.isoformat(),
        'maintenance_details': record.maintenance_details,
        'created_at': record.created_at.isoformat(),
    }
