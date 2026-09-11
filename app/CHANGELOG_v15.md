# CHANGELOG_v15：移除确认码（第一版评价方案残留）

## 背景
confirm_code（确认码）是第一版评价方案的产物：卖家凭一串码向买家确认交易。
当前交易评价模式已演进为「购买填交易地址 → 卖家确认交易 → 评价解锁」
（命名：确认制评价闭环 / 确认锁），确认动作由 orders 表状态
`pending → confirmed` 驱动，确认码已无任何校验入口、无输入框，
仅剩首页弹窗的展示徽标，属死功能。

## 改动（共 5 处）
- `app_v3.py`：删除 init_db 中 products.confirm_code 列的
  SHOW COLUMNS / ALTER TABLE（新建库不再包含该列）。
- `routes/products.py`：
  - 商品详情 API SELECT 中删除 p.confirm_code 列；
  - 删除「确认码仅卖家本人可见」返回逻辑；
  - 同步调整后续字段索引（seller_nickname、evaluation、tags 等 -1）。
- `templates/home/index.html`：
  - 删除详情弹窗转义列表中的 confirm_code；
  - 删除卖家侧"确认码"徽标展示。

## 影响确认（已核对代码）
- 购买填地址：写 orders.contact，不涉及 confirm_code → 无影响。
- 卖家确认交易：order_service.confirm_order 只更新 orders.status → 无影响。
- 评价门槛：evaluate 只校验 orders.status='confirmed' → 无影响。
- 唯一可见变化：首页弹窗不再显示"确认码"徽标（原为纯展示）。

## 验证
- 23 个 Python 文件 py_compile 全部通过。
- 全库代码 grep 无 confirm_code / 确认码 残留。
- 应用启动：35 路由注册、16 模板编译、首页/登录页 200。
- 登录态请求 /api/product：返回 18 个字段，confirm_code 已移除，其余字段完整。
- 测试商品数据已清理。

## 提示
已有数据库中的 products.confirm_code 列不会被自动删除（仅停止创建）。
如需彻底清理旧库，可手动执行：
    ALTER TABLE products DROP COLUMN confirm_code;
不影响运行，可留可删。
