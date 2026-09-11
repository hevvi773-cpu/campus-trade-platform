"""统一未读角标：消息 / 订单 / 反馈。

三个入口的未读口径各不相同，集中在此处定义，避免各处各写一份导致口径漂移。
"""

import pymysql

def get_badge_counts(db_config, username):
    """返回 {'message': n, 'order': n, 'feedback': n}，无用户时全 0。

    角标只是锦上添花：任何异常都退化成 0，绝不能把页面带成 500。
    """
    counts = {'message': 0, 'order': 0, 'feedback': 0}
    if not username:
        return counts

    try:
        conn = pymysql.connect(**db_config)
    except Exception:
        return counts

    cursor = conn.cursor()
    try:
        # 未读私信：别人发给我的、我还没读的
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE receiver=%s AND is_read=0",
            (username,),
        )
        counts['message'] = cursor.fetchone()[0] or 0

        # 待处理订单：我作为卖家待确认的（买家下的单等卖家处理）
        cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE seller=%s AND status='pending'",
            (username,),
        )
        counts['order'] = cursor.fetchone()[0] or 0

        # 未读反馈：管理员已回复但我还没看的
        cursor.execute(
            "SELECT COUNT(*) FROM feedbacks "
            "WHERE username=%s AND status='resolved' AND reply IS NOT NULL "
            "AND reply<>'' AND (is_read=0 OR is_read IS NULL)",
            (username,),
        )
        counts['feedback'] = cursor.fetchone()[0] or 0
    except Exception as exc:
        # 典型场景：feedbacks.is_read 列尚未迁移，此时反馈角标按 0 处理
        print(f"[badge] count failed: {exc}")
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

    return counts

def get_nickname(db_config, username):
    """取昵称，查不到时退回用户名本身。任何异常都退化成用户名，不抛。"""
    if not username:
        return ''

    try:
        conn = pymysql.connect(**db_config)
    except Exception:
        return username

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT nickname FROM users WHERE username=%s",
            (username,),
        )
        row = cursor.fetchone()
        return (row[0] or username) if row else username
    except Exception:
        return username
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

def get_user_favorite_ids(db_config, username):
    """当前用户已收藏的商品 id 集合。

    favorites 表存的是 username（不是昵称）。曾因传昵称导致首页爱心恒为未收藏态。
    查不到时返回空集合（表现为全部未收藏），不抛异常。
    """
    if not username:
        return set()

    try:
        conn = pymysql.connect(**db_config)
    except Exception:
        return set()

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT product_id FROM favorites WHERE username=%s",
            (username,),
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception as exc:
        print(f"[favorite] load failed: {exc}")
        return set()
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

def mark_feedbacks_read(db_config, username):
    """用户进入反馈页后，把已回复的反馈标记为已读。

    若 is_read 列尚未迁移则静默跳过，绝不能因此让反馈页 500。
    """
    if not username:
        return

    try:
        conn = pymysql.connect(**db_config)
    except Exception:
        return

    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE feedbacks SET is_read=1 "
            "WHERE username=%s AND status='resolved' AND reply IS NOT NULL AND reply<>''",
            (username,),
        )
        conn.commit()
    except Exception as exc:
        print(f"[feedback] mark read failed: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
