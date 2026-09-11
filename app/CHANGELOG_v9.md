# fix_patch_v9 变更说明

> 基于 fix_patch_v8 重构 + 新增需求。v7→v8 经核对仅为 1 行 bugfix 补丁（补传 `db_config` 参数），非版本迭代；v9 在 v8 基础上做结构重构与功能新增。

## 1. 代码结构重构（不改既有功能）
- 将单文件 `app_v3.py`（原约 7600 行，其中约 6300 行为空行膨胀）拆分为：
  - `app_v3.py`：仅保留 helpers、app 初始化、`ensure_schema()`
  - `routes/`：`auth.py`、`home.py`、`products.py`、`favorites.py`、`profile.py`、`admin.py`、`messages.py`、`orders.py`、`feedback.py`
  - `services/`：`authz.py`（权限工具）、`message_service.py`、`notify_service.py`、`order_service.py`、`audit_service.py`、`auth_service.py`、`feedback_service.py`、`student_id.py`
- 导入冒烟测试通过：35 条路由全部正确注册，与 v8 一致。

## 2. 新增权限分级（三级）
- **游客 guest**：仅可浏览首页；收藏 / 查看详情 / 购买 / 私聊 / 发布商品 均被拦截
  - 前端：`guestGuard()` 拦截点击并跳转登录
  - 后端：各写接口内联登录校验；`/api/product/<pid>` 对非登录用户返回 403
- **被禁言用户 muted**（`ban_until > now` 的已登录 student）：可看个人中心，但收藏 / 发消息 / 发布 / 购买 被禁用
  - 后端：`is_muted(db_config)` 校验，命中返回禁言页 / 403
- **正常用户 / 管理员**：无限制
- 权限判定集中在 `services/authz.py`（`is_muted` / `get_user_ban_state` / `get_user_kind` 及 `require_login` / `require_student` / `require_not_muted` / `admin_required` 装饰器）。

## 3. 聊天商品卡片
- 从 **商品详情页 / 首页 / 订单页** 点进聊天时，自动居中插入该商品信息卡片（带 `product_id`）；
- 直接从 **消息列表** 点进聊天时不插入；
- 实现：`chat_detail` 进入时 `_seed_product_card_if_absent()` 去重 seed 一条占位消息，`_enrich_product_messages()` 批量补全价格 / 图片供模板渲染居中卡片。

## 4. 删除「分享」功能
- 移除 `shareLink` / `openChatShare` / `sendChatShare` / `shareToQQ` / `shareToWechat` / `copyText` 等 JS 函数、`window.__share` 初始化、以及详情弹窗的 `share-row` 区块；
- 保留「收藏」按钮。

## 5. 清理
- 移除 3 处未使用的 authz 导入（`favorites.py` / `home.py` / `products.py`）。

---

## 6. 部署前修复（关键：补齐 v8 包漏带的文件）

你最初提供的 `fix_patch_v8.tar.gz` 是**残缺的 18 文件子集**，实际缺失：
- 4 个 service：`auth_service.py`、`order_service.py`、`audit_service.py`、`feedback_service.py`（上一版用「占位 stub」顶上，导致登录/注册/订单/详情/发消息全部失效）
- 4 个模板：`auth/login.html`、`auth/fill_student_id.html`、`favorites/index.html`、`products/evaluate.html`
- `wsgi.py`（你的 systemd 服务用 `gunicorn wsgi:application`，缺它服务起不来）
- `permission_service.py`（v8 已有的权限分级，本版用等价的 `services/authz.py` 统一收口）

已从完整 v8 源码找回真实实现并补齐、逐项核对：
- ✅ 4 个 service 替换为真实实现（含真实 SQL）
- ✅ 4 个模板 + `wsgi.py` 补齐；全量 `render_template` 引用交叉核对无缺失
- ✅ 补上订单下单的禁言拦截（`is_muted`，与 v8 的 `can_interact` 一致）
- ✅ `app_v3.py` 的 `debug=True` → `debug=False`（消除误用 `python app_v3.py` 上线时的 RCE 风险）
- ✅ 冒烟测试通过：35 路由 + `wsgi:application` 导入正常

## 已知遗留（非本次引入）
- `init_db` 需要 `cryptography`（MySQL 8 默认 caching_sha2 认证）：已加入 requirements.txt，部署时 `pip install cryptography`。
- 审计标记的 8 处 SQL 均为 v8 既有（f-string 拼**静态列名** + 参数化值），本次未改动；新增查询均参数化。
- 部分函数过长 / 圈复杂度偏高（`home.index`、`profile`、`admin_panel` 等）：v8 原有，未重构。
