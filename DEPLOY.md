# RPA 项目管理系统 · Docker 部署手册

> 适用对象：把本项目部署到内网服务器（如 172.16.30.159）的运维/开发同事。
> 全部命令在**服务器**上执行，Windows / Linux 均可（需已装 Docker）。

## 1. 架构总览

```
浏览器 ──► [frontend 容器] nginx:80      静态页面（vite 构建产物）
   │
   └────► [backend 容器] waitress:5000   Flask 接口（16 线程）
                 │                        │
                 │                        └─ /app/var（挂载到宿主机 backend/var）
                 │                             ├─ assets.db   仅作为历史迁移源
                 │                             └─ uploads/    需求附件
                 └──► MySQL 172.16.50.20:3306/rpa_web
                                           └─ assets   Skill/Python 统一资产表
```

- 前端产物在构建期写入后端地址；本项目部署值为 `http://172.16.50.20:5090`，浏览器直连后端 5090 端口。
- 整套编排里唯一有状态的目录是 `backend/var`，已通过 volume 落在宿主机；MySQL 数据不在容器里。

## 2. 前置条件

1. 服务器已安装 **Docker**（含 compose 插件）。验证：
   ```bash
   docker --version && docker compose version
   ```
   没装的话：Linux 用各发行版官方源安装 `docker-ce`，Windows 装 Docker Desktop。
2. 服务器能连通 MySQL：`172.16.50.20:3306`（后端启动后第一次查询时才会用到）。
3. 8090 和 5090 端口未被占用（被占用的处理见第 7 节）。

Docker 启动前必须把根目录 `.env.example` 复制为 `.env`，并填写
`RPA_DATABASE_URI`。Compose 不再接受缺失的数据库地址，后端启动时还会再次校验
目标必须是 `172.16.50.20:3306/rpa_web`。

## 3. 首次部署

```bash
# ① 把整个项目目录放到服务器上（git clone 或直接拷贝，均可）
cd /path/to/RPAweb

# ② 构建并后台启动（首次构建需拉基础镜像和依赖，约 3~10 分钟）
docker compose up -d --build

# ③ 看两个容器是否都是 Up 状态
docker compose ps
```

> **国内网络提示**：如果构建卡在 `pip install` 或 `npm ci`，打开
> `backend/Dockerfile` / `frontend/Dockerfile` 里注释掉的镜像源行（阿里云 pypi / npmmirror），
> 再重新 `docker compose up -d --build`。

## 4. 部署验证清单

逐条过一遍，全绿才算部署完成：

```bash
# 后端存活
curl http://127.0.0.1:5000/public/ping        # 预期 {"message":" public sussess"}

# 后端能查到主库数据（返回 JSON 且 success:true）
curl -s http://127.0.0.1:5000/public/projects | head -c 200

# 前端页面
curl -sI http://127.0.0.1/ | head -n 1        # 预期 HTTP/1.1 200

# vue-router 深层路径直达不 404（history 模式回落是否生效）
curl -sI http://127.0.0.1/main/RpaProgress | head -n 1   # 预期 200
```

浏览器里再确认：打开 `http://<服务器IP>/`，首页有项目/需求数据、标签页图标是公司 logo、能正常登录进用户端。

## 5. 日常更新发布

代码有改动后：

```bash
cd /path/to/RPAweb
git pull                      # 或用新代码覆盖目录
docker compose up -d --build  # 只重建有变化的镜像并滚动替换
```

- 前端有内容哈希 + nginx 缓存策略，用户刷新即可拿到新版本；标签页图标这类文件浏览器缓存较顽固，必要时 Ctrl+F5。
- 后端重启期间接口会中断几秒，尽量避开使用高峰。

## 6. 数据持久化与备份

| 数据 | 位置 | 备份方式 |
|---|---|---|
| 项目/需求/用户等主业务数据 | MySQL 172.16.50.20（容器外） | 按现有数据库备份策略 |
| Skill/Python 插件资产登记 | MySQL `172.16.50.20/rpa_web.assets` | 按主库备份策略 |
| 需求附件 | 宿主机 `backend/var/uploads/` | 直接拷贝该目录 |

`docker compose down`、重建镜像、升级容器都**不会**丢 `backend/var` 里的数据；只有手动删除宿主机目录才会丢。

## 7. 常见问题

**80 或 5000 端口被占用**
改 `docker-compose.yml` 里的端口映射左侧（宿主机端口），例如 `"8080:80"`。注意：改了 5000 的对外端口，前端构建参数里的后端地址也要跟着改（见下一条）。

**部署到别的机器 / 后端地址变了**
前端产物里的后端地址是构建期写死的。在 `docker-compose.yml` 里打开注释并改成实际地址：
```yaml
  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: http://<服务器IP>:5000
```
然后 `docker compose up -d --build` 重新构建前端。

**构建拉依赖超时/报 SSL 错**
用 Dockerfile 里注释的国内镜像源（见第 3 节提示）。

**接口报 "MySQL server has gone away" 或连接类错误**
先确认容器内能通数据库：`docker compose exec backend python -c "import pymysql;pymysql.connect(host='172.16.50.20',port=3306,user='<db-user>',password='<db-password>',database='rpa_web');print('ok')"`。连接池已配置自动探活/回收（backend/app/config.py），正常不应再出现闲置断连。

**时间显示差 8 小时**
backend 容器已设 `TZ=Asia/Shanghai`。历史代码里 `datetime.utcnow()` 和 `datetime.now()` 混用，个别旧记录时间偏差属已知现象，与部署无关。

## 学习周报模块：配置、备份与启动

### SQLite 数据与备份

历史 `backend/var/assets.db` 仅供迁移和核对，不再由运行中的网站读取。需要保存旧库时，可在 PowerShell 中备份确切文件：

```powershell
$assetDb = (Resolve-Path -LiteralPath 'D:\RPAweb\backend\var\assets.db').Path
$backup = "$assetDb.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $assetDb -Destination $backup
Get-Item -LiteralPath $assetDb,$backup | Select-Object FullName,Length
```

确认 source 与 backup 都存在且 `Length` 相同后才重启。Docker 必须持续挂载整个 `backend/var`，以保留数据库与令牌密钥。

### 环境变量与密钥权限

在 backend 启动的同一进程/容器环境设置（真实邮箱、密钥绝不写入代码）：

```powershell
$env:INITIAL_BOSS_EMAILS = 'approved-boss@example.com'
$env:LEARNING_TOKEN_SECRET = '<secret-from-approved-secret-store>'
$env:LEARNING_TOKEN_MAX_AGE_SECONDS = '43200' # 默认 12 小时
```

`INITIAL_BOSS_EMAILS` 只匹配已注册邮箱、只创建缺失老板映射、不覆盖已有角色；零匹配/零老板允许。未提供 `LEARNING_TOKEN_SECRET` 时后端复用 `backend/var/learning_token_secret.key`。POSIX 要求 owner-only `0600`；Windows 会重置 DACL、移除继承并仅授予运行账户，无法执行时后端以配置失败处理。

### 找回密码邮件

用户端和管理员端共用注册邮箱找回密码。重置链接默认 15 分钟有效，成功修改密码后立即失效。
项目已按阿里企业邮箱配置默认使用 `smtp.qiye.aliyun.com:465` 和 SSL。在启动 backend
的同一环境填写发件账号和 SMTP 客户端密码：

```powershell
$env:PASSWORD_RESET_FRONTEND_URL = 'http://<服务器IP>:8090'
$env:PASSWORD_RESET_SMTP_HOST = 'smtp.qiye.aliyun.com'
$env:PASSWORD_RESET_SMTP_PORT = '465'
$env:PASSWORD_RESET_SMTP_USERNAME = 'aitools@your-company.com'
$env:PASSWORD_RESET_SMTP_PASSWORD = '<smtp-client-password>'
$env:PASSWORD_RESET_SMTP_USE_TLS = 'false'
$env:PASSWORD_RESET_SMTP_USE_SSL = 'true'
$env:PASSWORD_RESET_EMAIL_FROM = 'aitools@your-company.com'
$env:PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = '900'
```

根目录的 `.env.example` 也提供了 Docker Compose 模板，可复制为 `.env` 后填写真实账号。
SMTP 密码只能放在部署环境或密钥管理系统中；如果阿里邮箱启用了客户端专用密码，
这里应填写客户端密码/授权码，而不是把个人登录密码写入代码。
`PASSWORD_RESET_EXPOSE_TOKEN` 只供自动化测试，生产环境严禁开启。

### 启动与待执行验证

```powershell
Set-Location 'D:\RPAweb\backend'; .\venv\Scripts\python.exe run.py
Set-Location 'D:\RPAweb\frontend'; npm.cmd run dev -- --host 0.0.0.0

Set-Location 'D:\RPAweb\backend'; .\venv\Scripts\python.exe -m pytest -q
Set-Location 'D:\RPAweb\frontend'; npm test; npm run build
curl.exe -sS -o NUL -w "backend %{http_code}`n" http://127.0.0.1:5000/public/ping
curl.exe -sS -o NUL -w "frontend %{http_code}`n" http://127.0.0.1:5173/
```

这些命令和浏览器四角色验收尚未由本文档宣称完成。发布前应使用经批准的 employee、intern、HR、boss 账户验证入口/直达路由、草稿/提交/退回/逾期、统计趋势、角色审计及学习 401/403/409/422 行为。学习入口是 `/main/LearningReport`、`/admin/LearningStats`、`/admin/RoleManagement`；既有非学习 admin 路由保留之前认证语义。统计仅计算最新有效正式提交，周一名册快照创建后冻结（包含零实习生周）。

## 8. 运维命令速查

```bash
docker compose ps                    # 容器状态
docker compose logs -f backend       # 跟踪后端日志（含每条请求）
docker compose logs -f frontend      # nginx 访问日志
docker compose restart backend      # 单独重启后端
docker compose down                  # 停止并移除容器（数据不丢，见第 6 节）
docker compose up -d --build         # 重建 + 启动
```

---

## 附：不用 Docker 的裸机部署（对照）

服务器上也可以不用 Docker 直接跑（当前 172.16.30.159 即此方式）：

1. 后端：Python 3.10+ 建 venv → `pip install -r backend/requirements.txt` → `python backend/run.py`（默认即 waitress 多线程，监听 0.0.0.0:5000；调试才设 `FLASK_DEBUG=1`）。
2. 前端：本地 `npm run build` 后，把 `frontend/dist/` 交给任意静态服务器托管；**必须**配置 history 路由回落（nginx 写法见 `frontend/nginx.conf` 的 `try_files` 一段），否则刷新深层路径会 404。
