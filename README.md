# 校园二手交易平台 🛒

> 面向高校学生的半封闭社区 C2C 二手交易系统，Flask + MySQL 全栈实现，已部署公网上线。

## 🌐 在线体验

- **线上地址**：http://106.53.27.244（域名办理中）
- 支持直接注册账号，体验注册→发布→下单→私信→评价完整流程
- 响应式适配桌面 / 平板 / 手机三档断点

## 🎯 项目背景

校园二手交易信息分散在 QQ 群、校园频道、表白墙等多个渠道，存在三个核心痛点：

- **找东西难**：信息频繁被刷屏淹没，要翻很久才能找到目标商品
- **状态不透明**：不清楚商品是还在、已售，还是太久没人买已经丢了
- **检索能力不一**：各渠道有的支持关键字搜索，有的完全不支持

本平台将分散的信息集中到统一入口，提供商品发布、审核、检索、下单、私信、评价的完整交易闭环。

## ✨ 核心功能

### 商品与交易

- 商品发布与审核（24h 未审核自动过审兜底）
- 商品搜索 + 标签筛选 + 三 Tab 分类（出售中 / 求购中 / 已售出）
- 订单交易（`SELECT ... FOR UPDATE` 行级锁防并发抢单与超卖）
- 站内私信（从商品进入自动携带商品上下文，聊天流中渲染居中商品卡片）
- 收藏（前端乐观更新 + 后端响应校正）
- 评价体系（买家评价卖家，1-5 星，个人中心展示发出/收到的评价与星级分布）

### 用户与权限

- 三级权限体系：游客 / 被禁言学生 / 正常学生 / 管理员，权限判定统一收口到 `services/authz.py`
- 登录限流（同一用户名 + IP 连续失败 5 次锁定 10 分钟）
- 全站 CSRF 防护（表单 `_csrf_token` / JSON 接口 `X-CSRF-Token`）
- 密码 werkzeug 哈希存储，Session Cookie `HTTPOnly + SameSite=Lax`

### 管理后台

- 商品审核（单条 / 批量通过、驳回、删除）
- 用户管理（禁言 / 解禁 / 注销，禁言时长固定 7 天）
- 反馈管理（回复用户反馈，用户侧产生未读角标）
- 数据看板（近 7 天发布量 / 成交额 / 注册量趋势、成交额 TOP5 卖家、活跃度明细）

### 个人中心

- 交易统计（已售 / 已买件数与金额）
- 数据可视化（近 6 个月月度交易柱状图、个人星级分布）
- 我发布的商品管理（状态下拉筛选、删除）
- 评价记录（我发出的 / 我收到的）

## 🛠 技术栈

| 层 | 选型 |
|---|---|
| 后端框架 | Flask 3.1（Blueprint 拆分：messages / orders / feedback） |
| 数据库 | MySQL 8（utf8mb4，PyMySQL 驱动） |
| 模板引擎 | Jinja2 + Bootstrap 5.3（CDN） |
| 图表 | Chart.js（CDN） |
| 部署 | gunicorn + systemd，云服务器 |
| 安全 | werkzeug 密码哈希、全站 CSRF、登录限流、三级权限 |
| 密码认证 | cryptography（MySQL caching_sha2_password） |

## 📁 项目结构

```
app/
├── app_v3.py              # Flask 应用入口、DB 配置、ensure_schema() 自动迁移
├── wsgi.py                # gunicorn 入口
├── csrf.py                # CSRF 初始化
├── requirements.txt       # 依赖清单
├── .env                   # 环境变量（数据库 / 密钥 / 管理员密码）
├── routes/                # 9 个路由模块
│   ├── auth.py            # 登录 / 注册 / 登出 / 填学号
│   ├── home.py            # 首页（搜索 / 标签 / AJAX 分页）
│   ├── products.py        # 发布 / 详情 API / 标记已售 / 评价
│   ├── favorites.py       # 收藏
│   ├── profile.py         # 个人中心
│   ├── admin.py           # 管理后台
│   ├── messages.py        # 私信（Blueprint）
│   ├── orders.py          # 订单（Blueprint）
│   └── feedback.py        # 意见反馈（Blueprint）
├── services/              # 11 个业务服务模块
│   ├── authz.py           # 权限判定与装饰器（唯一实现）
│   ├── auth_service.py    # 认证与登录限流
│   ├── product_service.py # 商品查询公共逻辑
│   ├── order_service.py   # 订单状态机与并发控制
│   ├── message_service.py # 私信与会话聚合
│   ├── notify_service.py  # 未读角标统一计算
│   ├── profile_service.py # 个人中心数据组装
│   ├── feedback_service.py
│   ├── audit_service.py   # 四类审计日志
│   ├── constants.py       # 全局常量
│   └── student_id.py
├── templates/             # Jinja2 模板（按模块分目录，含公共片段 _badges.html）
└── static/                # 静态资源（JS / 用户上传文件）
```

## 🏗️ 工程亮点

### 代码演进

- 从单文件 `app_v3.py`（7619 行）重构为模块化架构（9 路由 + 11 服务 + 模板分目录）
- 累计 15 个版本迭代，每个版本附 CHANGELOG 记录
- v14 结构重构，v15 清理已放弃的 confirm_code（确认码）设计残留（5 处清理，全库 grep 无残留）

### 质量与安全

- **P0 修复**：v3 修复管理后台 `onclick` 属性引号冲突，导致审核 / 禁言 / 注销按钮全部点击失效
- **500 热修**：v8 修复首页 `get_user_favorite_ids` 缺传 `db_config` 参数导致首页 500
- **越权修复**：v12 修复 confirm_code 越权漏洞（此前任何登录用户都能从详情接口读到确认码），v15 彻底移除该死功能
- **并发安全**：下单使用行级锁 + 影响行数校验，防止超卖与重复下单
- **全站 CSRF**：所有 POST 请求强制 token 校验
- **登录限流**：同一用户名 + IP 连续失败 5 次锁定 10 分钟
- **SQL 优化**：管理后台统计查询从 35 次降至 11 次（统计卡片 4 + 日指标 4 + TOP5 1 + 列表 2）

### v15 验证结果

- 23 个 Python 文件 `py_compile` 全部通过
- 35 条路由注册、16 个模板编译
- 首页 / 登录页 HTTP 200
- `/api/product` 返回 18 个字段，confirm_code 已移除，其余字段完整

## 📊 真实数据

| 指标 | 数值 |
|---|---|
| 注册用户 | 24 个（单人多账号全流程交叉验证） |
| 商品总数 | 51 件（待审核 2 / 已上架 47 / 已驳回 2） |
| 已售出 | 17 件（17 笔完整交易闭环） |
| 代码版本 | 15 个 |
| 路由数量 | 35 条 |
| 数据表 | 11 张 |
| 管理后台统计 SQL | 35 次 → 11 次 |
| 已跑通闭环 | 注册→发布→审核→下单→确认→评价 |

> 出于隐私合规考虑，未大规模公测；以上数据来自单人多账号交叉验证。

## 📐 设计文档

所有设计文档位于 `docs/` 目录，可直接在浏览器中打开：

| 文档 | 说明 |
|---|---|
| [PRD V1.3](docs/校园二手交易平台_PRD_V1.3.md) | 完整产品需求文档（106KB），含版本演进、11 张表 DDL、API 契约、隐私合规、20 条回归清单、DEV-001~013 遗留问题 |
| [部署架构图](docs/01_部署架构图.html) | 系统整体部署架构与技术选型 |
| [ER 图](docs/02_ER图.html) | 数据库实体关系设计（11 张表） |
| [核心业务流程图](docs/03_核心业务流程图.html) | 发布→下单→确认→评价全流程 |
| [状态机图](docs/04_状态机图.html) | 商品审核 / 交易 / 订单 / 反馈状态流转 |
| [项目目录结构图](docs/05_项目目录结构图.html) | 代码组织与模块划分 |
| [用户角色权限图](docs/06_用户角色权限图.html) | 游客 / 禁言 / 正常学生 / 管理员权限矩阵 |

## 🚀 快速开始

### 环境要求

- Python 3.9+
- MySQL 8.0+

### 本地运行

```bash
# 1. 解压代码包
tar -xzf fix_patch_v15_no_confirm_code.tar.gz
cd app

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
# 复制 .env.example 为 .env，然后修改以下配置：
cp .env.example .env
#   SECONDHAND_DB_HOST / PORT / USER / PASSWORD / NAME
#   SECONDHAND_SECRET_KEY
#   SECONDHAND_ADMIN_PASSWORD

# 4. 启动开发服务器
flask run
# 或生产模式
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

访问 http://localhost:5000

> 首次启动会自动执行 `ensure_schema()` 创建数据库表结构（模块导入时执行，保证生产环境新列自动补全）。

### 线上部署

```bash
# 生产环境：gunicorn + systemd
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

线上地址：http://106.53.27.244（域名办理中）

## 🔐 安全说明

- 密码使用 werkzeug `generate_password_hash` 哈希存储，登录用 `check_password_hash` 校验
- Session Cookie 设置 `HTTPOnly=True`、`SameSite=Lax`，`SECURE` 可通过环境变量配置
- 所有 POST 请求强制 CSRF 校验，缺失或校验失败返回 403
- 图片上传经扩展名 + MIME 双重校验，单文件 5MB 上限，请求体总上限 15MB
- SQL 全部参数化，仅允许 f-string 拼接静态列名
- 开放重定向防护：`next` 参数仅允许以单个 `/` 开头的站内相对路径

> ⚠️ **重要**：代码包中的 `.env` 包含开发环境配置（数据库密码、SECRET_KEY、管理员密码）。公网部署前请务必修改这些敏感信息，并不要将真实 `.env` 提交到公开仓库。

## 👤 作者

**陆慧慧（VER）**

- 西南大学 · 大数据管理与应用
- 求职方向：AI 产品经理 / 产品经理
- GitHub：[@hevvi773-cpu](https://github.com/hevvi773-cpu)

### 项目角色

- **课程作业阶段**：负责后端 + 网页端开发（队友负责小程序前端，其余成员负责实验日志与报告）
- **后续阶段**：独立完成十几次优化改造 + 公网部署 + PRD 文档整理（实现对齐型，逆向整理 13 个历史版本）

## 📄 许可证

MIT License
