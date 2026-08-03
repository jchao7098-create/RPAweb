# RPA 项目管理系统（AI Tools web）

内网使用的 RPA 项目全生命周期管理平台：需求提交与审核、开发进度公示、维护记录，
以及员工代码资产（Skill 文件 / Python 插件）的登记、审核与公开看板。

## 架构

```
浏览器 ──► 前端（Vue 3 + Vite，静态站点，:80）
   │
   └────► 后端（Flask + waitress，:5000）
                ├─► MySQL 172.16.50.20:3306/rpa_web
                │      └─ assets              Skill/Python 资产统一表
                └─► backend/var/assets.db     仅保留为历史迁移源
```

- 前端构建为纯静态文件，浏览器直连后端 5000 端口（CORS 已放开），不经反向代理。
- 主 MySQL 是**共享生产库**，本机开发也直连它——写操作要有生产意识。
- Skill/Python 资产统一写入 DBserver 的 `rpa_web.assets`，生产环境禁止回退到 SQLite。

## 目录结构

```
frontend/
  src/
    api/            axios 实例（http.js，统一超时与地址）与接口封装
    assets/         theme.css —— 全站设计令牌与共享组件类（aitools-* / btn / chip / panel）
    components/
      admin/        管理员端各栏目页
      user/         用户端各栏目页
      department/   公开的部门看板页（RPA / Skill / 插件）
      layout/       ConsoleShell —— 用户端/管理员端共享的控制台外壳
    config/         assetTypes.js —— 资产类型声明式配置（新增资产类型改这里）
    router/         路由（除首页外全部懒加载）
    views/          页面级组件（首页 / 登录注册 / 两个控制台）
backend/
  app/
    config.py       数据库连接、连接池、资产库与上传目录配置
    models/         SQLAlchemy 模型（主库 + assets bind）
    routes/         public / user / admin 三个蓝图 + serializers.py 共享序列化
  run.py            入口：默认 waitress 多线程；FLASK_DEBUG=1 时为本机调试模式
  var/              历史迁移库、令牌密钥与上传文件
docs/               部署指南.docx（可分发版）
DEPLOY.md           Docker 部署手册（速查版）
docker-compose.yml  一键编排（前端 nginx + 后端 waitress）
```

## 本地开发

```bash
# 后端（Python 3.10+）
cd backend
python -m venv venv && venv/Scripts/pip install -r requirements.txt
venv/Scripts/python run.py            # waitress 监听 0.0.0.0:5000

# 前端（Node 20+）
cd frontend
npm ci
npm run dev                            # http://localhost:5173
```

`frontend/.env.development` 已把开发模式的接口指向 `127.0.0.1:5000`；
生产构建不读该文件，默认打内网地址（可用 `VITE_API_BASE_URL` 构建参数覆盖，见 DEPLOY.md）。

## 部署

推荐 Docker：`docker compose up -d --build`，详见 [DEPLOY.md](DEPLOY.md)；
可分发的完整版指南在 `docs/部署指南.docx`。

## 找回密码

用户端和管理员端登录页都提供“忘记密码”入口。系统向注册邮箱发送 15 分钟有效的重置链接；
链接成功使用一次后立即失效。新注册账号及重置后的密码使用 Werkzeug scrypt 哈希保存，
历史明文账号仍可兼容登录。

发信默认采用阿里企业邮箱 `smtp.qiye.aliyun.com:465`（SSL），部署时仍需通过环境变量
提供发件邮箱和 SMTP 客户端密码，完整示例见 [DEPLOY.md](DEPLOY.md)。未配置账号时接口会明确提示联系管理员，
不会返回或记录可用于生产环境的重置链接。

## 学习周报模块

学习周报与 Skill/Python 资产共用 `assets` bind，当前统一写入 DBserver 的 `rpa_web`。历史 `backend/var/assets.db` 仅供迁移和备份核对，不再由运行中的网站读取。

`LEARNING_TOKEN_SECRET` 是首选令牌密钥；未设置时后端首次启动生成并复用 `backend/var/learning_token_secret.key`。默认有效期为 12 小时（`LEARNING_TOKEN_MAX_AGE_SECONDS=43200`）。密钥文件必须随 `backend/var` 持久化：POSIX 为 owner-only `0600`；Windows 会删除继承和旧显式 ACL，仅保留运行账户 ACL，无法强制时后端会失败而不会降级为宽权限。

`INITIAL_BOSS_EMAILS` 是可选的、逗号分隔的已注册邮箱。启动只为匹配账户创建缺失的老板映射，不会覆盖已有角色；零匹配和零老板均合法。真实邮箱和密钥只放在启动环境，不能写入仓库。

学习令牌只用于 `/learning/*`。`/main/LearningReport` 仅对服务端授权的实习生/当前周名册成员可见；`/admin/LearningStats`、`/admin/RoleManagement` 仅供 HR/老板使用；普通员工无入口。既有非学习 admin 路由保持原认证行为。周一名册创建后冻结（包含零成员周）；草稿不计统计，统计只读取最新有效正式提交；退回记录可在截止前重提，逾期为 `return_expired` 并排除统计。所有学习日期按 `Asia/Shanghai` 显示。

## 代码约定

开发前请读根目录 [CLAUDE.md](CLAUDE.md)（前后端约定、已知限制、易错点），
其中的规则对人和 AI 协作者同样适用。
