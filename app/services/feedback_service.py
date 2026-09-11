import pymysql


class FeedbackError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _format_feedback(row, include_username=False):
    if include_username:
        return {
            'id': row[0],
            'username': row[1],
            'title': row[2],
            'content': row[3],
            'status': row[4],
            'reply': row[5],
            'created_at': row[6].strftime('%Y-%m-%d %H:%M') if row[6] else '',
            'image': row[7] or '',
        }

    return {
        'id': row[0],
        'title': row[1],
        'content': row[2],
        'status': row[3],
        'reply': row[4],
        'created_at': row[5].strftime('%Y-%m-%d %H:%M') if row[5] else '',
        'image': row[6] or '',
    }


def get_user_feedbacks(db_config, username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, title, content, status, reply, created_at, image
            FROM feedbacks
            WHERE username = %s
            ORDER BY created_at DESC, id DESC
            """,
            (username,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return [_format_feedback(row) for row in rows]


def get_all_feedbacks(db_config):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, username, title, content, status, reply, created_at, image
            FROM feedbacks
            ORDER BY created_at DESC, id DESC
            """
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return [_format_feedback(row, include_username=True) for row in rows]


def create_feedback(db_config, username, title, content, image_path=''):
    title = (title or '').strip()
    content = (content or '').strip()
    if not title or not content:
        raise FeedbackError('标题和内容不能为空')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO feedbacks (username, title, content, image)
            VALUES (%s, %s, %s, %s)
            """,
            (username, title, content, image_path or ''),
        )
        feedback_id = cursor.lastrowid
        conn.commit()
        return feedback_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def resolve_feedback(db_config, feedback_id, reply):
    reply = (reply or '').strip()
    if not reply:
        raise FeedbackError('回复内容不能为空')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE feedbacks
            SET reply = %s, status = 'resolved'
            WHERE id = %s
            """,
            (reply, feedback_id),
        )
        if cursor.rowcount != 1:
            raise FeedbackError('反馈不存在', 404)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
