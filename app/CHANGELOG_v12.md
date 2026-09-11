# v12 更新说明（代码质量重构，在 v11 基础上）

按"函数单一职责 / 消除重复 / 接口精简"三项原则重构，无功能变化。

## 1. 胖函数拆分
- **routes/home.py** 191→148 行：WHERE 拼装（`_build_visibility_where`）、行转换
  （`_rows_to_products`）、禁言查询（`_current_ban_until_text`，改用 authz.get_user_ban_state）
  全部拆出；查询落到 services.product_service。
- **routes/profile.py** 186→23 行：10+ 条查询全部搬到
  services/profile_service.load_profile_data；路由只剩登录校验+渲染。
  附带修复：账号被注销后访问 /profile 原来会 405（GET 跳 POST /logout），
  现在清会话回登录页。
- **routes/admin.py**：admin_panel 拆出 `_build_product_where` /
  `_get_overview_stats` / `_get_daily_metrics` / `_get_top_sellers`。
  **性能优化**：商品统计 8 次 COUNT → 3 次；近 7 天日指标
  7 天 × 5 指标 = 35 次循环 SQL → 4 次 GROUP BY。

## 2. 重复代码抽公共
- **services/constants.py（新）**：STATUS_MAP / SOLD_STATUS_MAP / TYPE_MAP /
  PRODUCT_TAGS / CREDIT_LEVELS 统一定义，app_v3 re-export 保持兼容。
- **services/product_service.py（新）**：标准商品 SELECT（BASE_SELECT）、
  通用分页 fetch_products_page、行→字典 product_row_to_dict、
  信用批量查询 get_credit_map。home/admin/favorites 三处重复块消除；
  **顺带修复 favorites 信用默认值 'C' 与首页 'B' 不一致的问题（统一 'B'）**。
- **services/authz.py**：新增 is_student_session()，messages/orders/feedback
  三个蓝图里各自复制的 require_student 全部删除复用。
- **products.py 发布/添加**：手写 ban_until 内联判断改为
  @require_not_muted 装饰器（禁言规则全站只剩 authz 一处实现）。
- **static/js/product_detail.js（新）**：详情弹窗渲染逻辑公共化，
  admin 与 profile 两个模板复用（首页弹窗带购买/私信按钮，保持独立）。

## 3. 接口字段精简
- **/api/product/<pid>**：
  - ⚠️ **confirm_code 交易确认码改为仅卖家本人可见**（此前无条件返回，
    买家可直接读接口拿到确认码，属安全漏洞）
  - 删除前端未使用的 id、status（原始码，前端只用 status_text）
- **/send_message**：删除前端未使用的 message_id（审计日志仍记录）

## 验证
- py_compile 全部通过；import 冒烟 35 条路由注册正常；
- 5 个关键模板假数据渲染通过；product_row_to_dict 字段断言通过。

## 部署
```
tar -xzf fix_patch_v12.tar.gz -C /home/ubuntu/my_dev
sudo systemctl restart secondhand
```
验证：`ls /home/ubuntu/my_dev/app/services/product_service.py` 存在即可。
