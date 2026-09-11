"""个人中心数据组装；用户不存在时返回 None。"""
from datetime import datetime, timedelta

import pymysql

from services.constants import SOLD_STATUS_MAP, STATUS_MAP

_DATE_FMT = "%%Y-%%m-%%d %%H:%%i"


def load_profile_data(db_config, username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT username, nickname, student_id FROM users WHERE username=%s",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        user_info = {'username': row[0], 'nickname': row[1], 'student_id': row[2]}

        cursor.execute(
            "SELECT IFNULL(COUNT(*),0), IFNULL(SUM(price),0) FROM products WHERE seller=%s AND sold_status='sold'",
            (username,),
        )
        sold_count, sold_total = cursor.fetchone()
        cursor.execute("""
            SELECT IFNULL(COUNT(DISTINCT p.id),0), IFNULL(SUM(p.price),0)
            FROM evaluations e JOIN products p ON e.product_id = p.id
            WHERE e.from_user=%s AND p.sold_status='sold'
        """, (username,))
        bought_count, bought_total = cursor.fetchone()
        stats = {
            'sold_count': sold_count or 0, 'sold_total': float(sold_total or 0),
            'bought_count': bought_count or 0, 'bought_total': float(bought_total or 0),
        }

        cursor.execute(f"""
            SELECT p.name, e.to_user, e.rating, e.content, DATE_FORMAT(e.created_at, '{_DATE_FMT}')
            FROM evaluations e JOIN products p ON e.product_id = p.id
            WHERE e.from_user=%s ORDER BY e.created_at DESC
        """, (username,))
        sent_evals = [
            {'product_name': r[0], 'to_user': r[1], 'rating': r[2], 'content': r[3], 'created_at': r[4]}
            for r in cursor.fetchall()
        ]
        cursor.execute(f"""
            SELECT p.name, e.from_user, e.rating, e.content, DATE_FORMAT(e.created_at, '{_DATE_FMT}')
            FROM evaluations e JOIN products p ON e.product_id = p.id
            WHERE e.to_user=%s ORDER BY e.created_at DESC
        """, (username,))
        received_evals = [
            {'product_name': r[0], 'from_user': r[1], 'rating': r[2], 'content': r[3], 'created_at': r[4]}
            for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT p.name, p.price, DATE_FORMAT(p.sold_time, '%%Y-%%m-%%d %%H:%%i'), o.id, o.status
            FROM products p
            LEFT JOIN orders o ON o.product_id=p.id AND o.status IN ('pending','confirmed')
            WHERE p.seller=%s AND p.sold_status='sold' ORDER BY p.sold_time DESC
        """, (username,))
        sold_products = [
            {'name': r[0], 'price': r[1], 'sold_time': r[2], 'order_id': r[3], 'order_status': r[4]}
            for r in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT id, name, price, status, sold_status, DATE_FORMAT(created_at, '{_DATE_FMT}')
            FROM products WHERE seller=%s ORDER BY id DESC
        """, (username,))
        my_products = [
            {
                'id': r[0], 'name': r[1], 'price': r[2],
                'status': r[3], 'status_cn': STATUS_MAP.get(r[3], r[3]),
                'sold_status': r[4],
                'sold_status_cn': SOLD_STATUS_MAP.get(r[4], r[4]),
                'created_at': r[5] or '',
            }
            for r in cursor.fetchall()
        ]

        # 近 6 个月月度交易
        cursor.execute("""
            SELECT DATE_FORMAT(sold_time, '%%Y-%%m'), COUNT(*) FROM products
            WHERE seller=%s AND sold_status='sold'
            GROUP BY DATE_FORMAT(sold_time, '%%Y-%%m') ORDER BY MIN(sold_time)
        """, (username,))
        monthly_sold_dict = {r[0]: r[1] for r in cursor.fetchall()}
        cursor.execute("""
            SELECT DATE_FORMAT(e.created_at, '%%Y-%%m'), COUNT(*)
            FROM evaluations e JOIN products p ON e.product_id = p.id
            WHERE e.from_user=%s AND p.sold_status='sold'
            GROUP BY DATE_FORMAT(e.created_at, '%%Y-%%m') ORDER BY MIN(e.created_at)
        """, (username,))
        monthly_bought_dict = {r[0]: r[1] for r in cursor.fetchall()}
        months = [(datetime.now() - timedelta(days=30 * i)).strftime('%Y-%m') for i in range(5, -1, -1)]

        cursor.execute(
            "SELECT rating, COUNT(*) FROM evaluations WHERE to_user=%s GROUP BY rating",
            (username,),
        )
        rating_dict = {r[0]: r[1] for r in cursor.fetchall()}

    finally:
        cursor.close()
        conn.close()

    return {
        'user_info': user_info,
        'stats': stats,
        'sent_evals': sent_evals,
        'received_evals': received_evals,
        'sold_products': sold_products,
        'my_products': my_products,
        'monthly_labels': months,
        'monthly_sold': [monthly_sold_dict.get(m, 0) for m in months],
        'monthly_bought': [monthly_bought_dict.get(m, 0) for m in months],
        'rating_dist': [rating_dict.get(i, 0) for i in range(1, 6)],
    }
