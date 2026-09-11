"""私信服务：会话列表、聊天明细、发消息。

历史上 messages.product_id 列是后加的，旧库未迁移时按两套 SQL 各写一遍；
现在统一为一套 SQL，用 SHOW COLUMNS 判断一次列是否存在，缺列时自动退回
不带商品的精简查询，避免复制两份几乎相同的代码。
"""
import pymysql


class MessageError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _has_product_column(db_config):
    """messages.product_id 列是否存在（旧库未迁移时为 False）。"""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM messages LIKE 'product_id'")
            return cursor.fetchone() is not None
    finally:
        conn.close()


def get_conversations(db_config, username):
    """会话列表：对方 + 最近一条消息 + 未读数 + 来源商品。"""
    return _get_conversations(db_config, username, _has_product_column(db_config))


def _get_conversations(db_config, username, with_product):
    if with_product:
        extra_cols = (
            "latest.product_id, pr.name AS product_name, "
            "COALESCE(u.nickname, peers.other_user) AS other_nickname"
        )
        extra_joins = (
            "LEFT JOIN products pr ON latest.product_id = pr.id "
            "LEFT JOIN users u ON u.username = peers.other_user"
        )
    else:
        extra_cols = "NULL AS product_id, NULL AS product_name, NULL AS other_nickname"
        extra_joins = ""

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            SELECT peers.other_user, latest.created_at, latest.content,
                   COALESCE(unread.unread_count, 0),
                   {extra_cols}
            FROM (
                SELECT
                    CASE WHEN sender = %s THEN receiver ELSE sender END AS other_user,
                    MAX(id) AS latest_id
                FROM messages
                WHERE sender = %s OR receiver = %s
                GROUP BY other_user
            ) peers
            JOIN messages latest ON latest.id = peers.latest_id
            {extra_joins}
            LEFT JOIN (
                SELECT sender AS other_user, COUNT(*) AS unread_count
                FROM messages
                WHERE receiver = %s AND is_read = 0
                GROUP BY sender
            ) unread ON unread.other_user = peers.other_user
            ORDER BY latest.created_at DESC, latest.id DESC
            """,
            (username, username, username, username),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return [
        {
            'other_user': row[0],
            'last_time': row[1].strftime('%m-%d %H:%M') if row[1] else '',
            'last_msg': row[2] or '',
            'unread_count': row[3] or 0,
            'product_id': row[4],
            'product_name': row[5] or '',
            'other_nickname': row[6] or row[0],
        }
        for row in rows
    ]


def get_chat_messages(db_config, username, other_user):
    """单会话明细：按时间正序，并把对方发来的标记为已读。"""
    other_user = (other_user or '').strip()
    if not other_user:
        raise MessageError('接收人不能为空')
    if other_user == username:
        raise MessageError('不能与自己对话')

    return _get_chat_messages(db_config, username, other_user, _has_product_column(db_config))


def _mark_incoming_read(db_config, username, other_user):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE messages
            SET is_read = 1
            WHERE receiver = %s AND sender = %s AND is_read = 0
            """,
            (username, other_user),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _get_chat_messages(db_config, username, other_user, with_product):
    _mark_incoming_read(db_config, username, other_user)

    if with_product:
        extra_cols = "m.product_id, p.name AS product_name"
        extra_joins = "LEFT JOIN products p ON m.product_id = p.id"
    else:
        extra_cols = "NULL AS product_id, NULL AS product_name"
        extra_joins = ""

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            SELECT m.sender, m.content,
                   DATE_FORMAT(m.created_at, '%%m-%%d %%H:%%i') AS created_at,
                   {extra_cols}
            FROM messages m
            {extra_joins}
            WHERE (m.sender = %s AND m.receiver = %s)
               OR (m.sender = %s AND m.receiver = %s)
            ORDER BY m.created_at ASC, m.id ASC
            """,
            (username, other_user, other_user, username),
        )
        rows = cursor.fetchall()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return [
        {
            'sender': row[0],
            'content': row[1],
            'created_at': row[2],
            'product_id': row[3],
            'product_name': row[4] or '',
        }
        for row in rows
    ]


def create_message(db_config, sender, receiver, content, product_id=None):
    """发消息，可携带来源商品 id（用于展示"对方从哪个商品点进来"）。"""
    receiver = (receiver or '').strip()
    content = (content or '').strip()

    if not receiver or not content:
        raise MessageError('接收人和内容不能为空')
    if sender == receiver:
        raise MessageError('不能给自己发消息')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO messages (sender, receiver, content, product_id) "
            "VALUES (%s, %s, %s, %s)",
            (sender, receiver, content, product_id),
        )
        message_id = cursor.lastrowid
        conn.commit()
        return message_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
