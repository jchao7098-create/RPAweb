# CLAUDE.md —— 代码约定与已知限制

面向后续维护者（人与 AI 均适用）。架构与目录见 [README.md](README.md)，部署见 [DEPLOY.md](DEPLOY.md)。

## 前端约定

- **接口请求一律走 `src/api/http.js` 的共享实例**（30s 超时、地址可用环境变量覆盖）。
  严禁在组件里 `import axios` 硬编码后端 IP——历史上这么写导致本地开发全挂过一次。
- **Element Plus 按需引入**：模板里的 `el-*` 组件和 `ElMessage`/`ElMessageBox` 由
  vite 的 unplugin 编译期自动注入（含样式）。**不要手写 `import { ElMessage } from 'element-plus'`**，
  显式引入会把整个组件库拖进该分包且样式不会自动挂上。
- **路由一律懒加载**（`() => import(...)`），只有首页 PublicView 同步引入。
- **样式走 `src/assets/theme.css` 的设计令牌**（`--brand-*` 变量）与共享类
  （`aitools-nav` / `btn` / `chip` / `panel`）。新公开页面复用这些类，不要另起炉灶。
- 用户端/管理员端的控制台外壳是共享组件 `components/layout/ConsoleShell.vue`，
  两个视图只传栏目清单和文案；改导航/欢迎页/页脚只改这一处。
- **新增资产类型**（如 Bot 模板）：在 `config/assetTypes.js` 加一条配置 + router 加一条路由即可，
  提交页与公开看板都是按配置渲染的。
- 首页滚动入场动画的 IntersectionObserver `threshold` 必须为 0：
  比例阈值会让高于视口数倍的区块永远无法显形（历史 bug）。

## 后端约定

- **主 MySQL（172.16.50.20/rpa_web）是共享生产库**：Skill/Python 资产必须写入
  `rpa_web.assets`。生产启动会校验 `assets` bind，禁止改回 SQLite 或其他数据库；
  `backend/var/assets.db` 仅保留为历史迁移源，不得作为运行时资产库。
- **列表接口必须预加载关联**：`selectinload(Project.logs).joinedload(ProjectLog.developer)`，
  否则退化为 N+1（曾经一次首页访问打出 500+ 条 SQL）。
- **实体序列化统一走 `routes/serializers.py`**，同一实体多接口返回时口径一致；
  管理端敏感字段（description/credentials）由 `include_admin_fields` 控制，公开接口绝不能开。
- `run.py` 默认 waitress 多线程（生产可用）；`FLASK_DEBUG=1` 才是调试模式且只绑 127.0.0.1。
  连接池参数已在 `config.py` 配好（pre_ping/recycle/池容量），不要删。
- 日志目前用 `print`（waitress + docker 下直接可见）；Blueprint 对象没有 `.logger` 属性，别用。

## 已知限制（改之前先看）

- **历史账号可能仍为明文密码**：新注册账号和找回密码后的账号已使用 Werkzeug scrypt 哈希；
  登录逻辑兼容两种格式，尚未批量迁移的旧账号会在下一次找回密码后完成升级。
  需求表中的业务系统 account/password 仍按历史结构保存。
- **数据库账号密码硬编码在 `backend/app/config.py`**，上 Git 前应迁到环境变量。
- **需求拒绝理由不落库**：requirements 表没有 reject_reason 列，管理端填写的理由不会保存。
- 公开资产接口（/public/assets）只返回"已通过"的资产——是有意设计，不是 bug。
- `models.py` 的 Progress 模型无任何路由使用（历史遗留表）。
- 本仓库**尚未初始化 git**，也没有 lint/测试基建。本机跑后端需自建 venv（见 README 本地开发一节）。

## 学习周报模块约定

- 学习 API 位于 `/learning`；组件只能经 `src/api/learning.js` 和共享 `src/api/http.js` 请求。仅 `/learning` URL 附加 Bearer learning token；仅学习 `401` 可清除 `learning_token`、`learning_role`、缓存 profile，不能影响既有登录 ID 或非学习接口。
- 学习令牌必须记录登录入口：`/user/login` 签发 `user`，`/admin/login` 签发 `admin`；旧格式令牌拒绝并要求重新登录。所有 `admin` 入口会话可查看学习统计与个人趋势，只有同时具备 `hr`/`boss` 角色的 `admin` 会话可退回周报、调整角色和查看角色审计；用户端周报接口仅接受 `user` 入口会话。
- 用户端登录必须提交 `employment_type=intern|employee`。无 `user_roles` 映射时首次选择写入并固定；首次实习生立即加入当周名册。已有映射只校验不覆盖，职位不一致返回 `409`，后续仅 HR/老板可修改。
- 路由/导航必须以 `GET /learning/me` 的服务端能力标记为准，缓存角色不具有权威性。学习 token 不承载可信角色；后端每次请求从本地 SQLite 读取当前角色。学习页面路由保持懒加载。
- 角色仅为 `employee`、`intern`、`hr`、`boss`；无映射默认 employee，登录/查询不得创建映射。HR 和老板都可分配四种角色，角色变更必须追加审计。
- 学习模块与资产模型共用 `assets` bind，当前统一写入 DBserver 的 `rpa_web`；
  `assets.db` 仅用于历史迁移和备份核对。
- `INITIAL_BOSS_EMAILS` 仅匹配已注册邮箱并只补缺失老板映射，不能覆盖角色，零匹配/零老板合法。`LEARNING_TOKEN_SECRET` 优先于持久化密钥文件，默认 TTL 43200 秒；密钥不得泄露。POSIX 密钥必须 `0600`；Windows 必须只保留服务账户的显式 ACL，保护失败应显式失败。
- 草稿、正式提交、退回版本不能混用。统计只读最新有效正式提交；草稿、缺失、退回和逾期均不计入提交指标。周名册一旦创建即冻结，角色变更仅影响后续未冻结周。

## 验证习惯

- 后端改动：重启后用真实请求验证（本机后端 + MySQL 直连可用）；
  改序列化/查询时用响应逐字节对比 + SQL 计数（参考会话内 verify_queries.py 的做法）。
- 前端改动：`npm run build` 必须通过；浏览器实测受影响页面（预览面板为隐藏标签页，
  截图与 rAF/IntersectionObserver 不可用，用 DOM/网络/computed style 验证）。
