from flask import Blueprint, jsonify, request
from app.models.models import db, Project, ProjectLog, Requirement, Asset
from sqlalchemy.orm import joinedload, selectinload

from .serializers import serialize_asset, serialize_project, serialize_requirement

bp = Blueprint('public', __name__)

# 获取所有开发项目（含日志）
@bp.route('/projects', methods=['GET'])
def get_all_projects():
    try:
        # 一次性预加载 logs 及每条日志的开发者，整个接口固定 2 条 SQL；
        # 否则每个项目查一次日志、每条日志再查一次用户，首页一次访问就是上千条查询
        projects = (
            Project.query
            .options(selectinload(Project.logs).joinedload(ProjectLog.developer))
            .order_by(Project.created_at.desc())
            .all()
        )
        return jsonify(success=True, data=[serialize_project(p) for p in projects])

    except Exception as e:
        return jsonify(success=False, message=str(e))




# 获取所有需求（公开口径，不含描述与账号密码）
@bp.route('/requirements', methods=['GET'])
def get_all_requirements():
    try:
        requirements = db.session.query(Requirement).all()
        return jsonify([serialize_requirement(r) for r in requirements])

    except Exception as e:
        print(f"Error while fetching requirements: {str(e)}")
        return jsonify({'error': '内部服务器错误', 'details': str(e)}), 500



# 公开看板：员工代码资产（返回全部已通过项，包括停用项目；不暴露存储路径）
@bp.route('/assets', methods=['GET'])
def get_public_assets():
    asset_type = request.args.get('asset_type')
    query = Asset.query.filter(Asset.status == '已通过')
    if asset_type:
        query = query.filter_by(asset_type=asset_type)
    assets = query.order_by(Asset.created_at.desc()).all()
    return jsonify({'data': [serialize_asset(a) for a in assets]})


@bp.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': ' public sussess'})
