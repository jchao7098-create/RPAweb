from app import db
from datetime import datetime
from sqlalchemy import Enum


# 用户表
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    created_projects = db.relationship('Project', backref='creator', lazy=True)
    developed_logs = db.relationship('ProjectLog', backref='developer', lazy=True)
    operated_logs = db.relationship('MaintenanceLog', backref='operator', lazy=True)

# 项目表
class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')
    progress = db.Column(db.Float, default=0.0)

    logs = db.relationship('ProjectLog', backref='project', lazy=True)

# 项目日志表
class ProjectLog(db.Model):
    __tablename__ = 'project_logs'

    id = db.Column(db.Integer, primary_key=True)
    log_time = db.Column(db.DateTime, default=datetime.utcnow)
    developer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    remark = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)




class MaintenanceItem(db.Model):
    __tablename__ = 'maintenance_items'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    progress = db.Column(db.Float, default=0.0)
    status = db.Column(Enum('维护中', '维护结束', name='maintenance_status'), default='维护中')  # 使用枚举类型
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship('MaintenanceLog', backref='maintenance', lazy=True)

# 维护日志表
class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'

    id = db.Column(db.Integer, primary_key=True)
    log_time = db.Column(db.DateTime, default=datetime.utcnow)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(Enum('维护中', '维护结束', name='maintenance_log_status'), nullable=False)  # 使用枚举类型
    remark = db.Column(db.Text)
    maintenance_id = db.Column(db.Integer, db.ForeignKey('maintenance_items.id'), nullable=False)


# 用户提交的需求表
class Requirement(db.Model):
    __tablename__ = 'requirements'  # 表名与数据库中一致
    user_id = db.Column(db.Integer)  # 提交人 id（历史表结构未建外键约束，勿按 FK 使用）
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 唯一标识需求
    title = db.Column(db.String(255), nullable=False)  # 需求标题
    description = db.Column(db.Text)  # 需求描述
    department = db.Column(db.String(255))  # 部门名称
    requester = db.Column(db.String(255))  # 需求人姓名
    feedback_time = db.Column(db.DateTime)  # 反馈时间
    priority = db.Column(db.Enum('高', '中', '低'), nullable=False)  # 紧急程度（高、中、低）
    expected_finish_time = db.Column(db.DateTime)  # 期望完成时间
    platform = db.Column(db.String(255))  # RPA平台/软件
    operation_link = db.Column(db.String(255))  # 操作链接
    account = db.Column(db.String(255))  # 登录账号
    password = db.Column(db.String(255))  # 登录密码
    attachments = db.Column(db.JSON)  # 附件列表（可以存储文件路径或 URL）
    status = db.Column(db.Enum('待审核', '已通过', '已取消', '已拒绝'))  # 审核状态，取值即枚举四项
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间

# 审核通过后的进度表
# 注意：当前没有任何路由使用此模型，对应的是历史遗留表；删除前需确认线上无依赖
class Progress(db.Model):
    __tablename__ = 'progresses'

    id = db.Column(db.Integer, primary_key=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey('requirements.id'), nullable=False)
    phase = db.Column(db.String(100), nullable=False)
    progress_detail = db.Column(db.Text)


class MaintenanceRecord(db.Model):
    __tablename__ = 'maintenance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    maintainer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    maintainer_name = db.Column(db.String(100), nullable=False)
    maintenance_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    project_name = db.Column(db.String(100), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requester_name = db.Column(db.String(100), nullable=False)
    maintenance_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# 员工代码资产表（Skill 文件 / Python 插件）
# 使用 assets bind；生产配置将该 bind 指向 RPA 主 MySQL，测试可覆盖为 SQLite。
class Asset(db.Model):
    __tablename__ = 'assets'
    __bind_key__ = 'assets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    asset_type = db.Column(db.String(32), nullable=False)  # 'skill' | 'python_plugin'
    name = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    submitter = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(50))
    description = db.Column(db.Text)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)  # 可选，当前仅登记文件名，暂为 None
    status = db.Column(db.Enum('待审核', '已通过', '已拒绝'), default='待审核', nullable=False)
    lifecycle_status = db.Column(
        db.Enum('在编', '使用', '大修', '停用'),
        default='在编',
        nullable=False,
    )
    progress = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    reject_reason = db.Column(db.Text)  # 拒绝理由，status='已拒绝' 时填写
