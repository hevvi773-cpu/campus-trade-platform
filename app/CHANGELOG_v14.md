# CHANGELOG_v14：代码清理版（基于 v13_no_credit）

按 v12/v13 代码体检结论清理，仅改结构不动行为。改动清单：

## 1. 合并消息服务双套查询（services/message_service.py）
- 原 `_get_conversations_with_product` / `_get_conversations_legacy`、
  `_get_chat_messages_with_product` / `_get_chat_messages_legacy` 两对几乎相同的
  SQL 各写一份，共约 90 行重复，靠 `except` 静默降级。
- 现改为：`SHOW COLUMNS FROM messages LIKE 'product_id'` 判一次列是否存在，
  单套参数化 SQL + 缺列时用 `NULL` 占位列，返回结构不变。
- 效果：文件 231 → 173 行；错误不再被静默吞掉（列真缺时也能正常工作）。

## 2. 删除孤儿列（app_v3.py init_db）
- users 表 `credit_score`、`credit_level` 两列随 v13 去信用后已无任何读写，
  删除对应的两处 SHOW COLUMNS / ALTER TABLE。

## 3. 清除死代码（app_v3.py）
- 删除从未使用的常量 `VALID_COLLEGE_CODES`、`LEVEL_MAX_YEARS`。
- 删除空壳函数 `get_conn()`（调用处统一改用 `connect_db()`）、
  `validate_student_id()`（仅转发 validate_username，无调用方）。
- 删除约 40 行删代码后遗留的占位注释（"===== 新增：私信模板 =====" 等）。
- 精简 import：去掉 random、functools.wraps、render_template、redirect、
  jsonify、url_for、secure_filename 及 auth_service 中未使用的导出
  （AuthError / authenticate_user / register_student / validate_username）。

## 4. 接口/模板传参瘦身（返回字段不变，只删死变量）
- `routes/home.py`：Ajax 加载更多不再返回 `next_page`（前端一直自算）；
  首页渲染不再传 `products`、`total_pages`（模板只用三个分组和 has_more）。
- `routes/messages.py`：chat_detail 不再传 `source_product`、`product_id`
  给模板（detail.html 从未使用）。
- `routes/favorites.py`：不再传 `identities`、`current_user`（模板只用
  current_username）。

## 验证
- 23 个 Python 文件 `py_compile` 全部通过。
- 全库 grep 无 `get_conn / VALID_COLLEGE_CODES / LEVEL_MAX_YEARS /
  validate_student_id / next_page / source_product / credit_*` 残留。
- 模板无 `products / total_pages / identities / credit_levels /
  source_product` 悬空引用；前端 URL 参数（product_id 跳转聊天等）原样保留。

## 统计（对比 v13）
- Python 总行数：2754 → 2641（-113 行）。
- message_service.py：231 → 173 行（-58 行）。
