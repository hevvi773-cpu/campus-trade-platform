"""商品查询公共逻辑：分页、行→字典、信用批量查询（home/admin/favorites 共用）。"""
import pymysql

from services.constants import SOLD_STATUS_MAP, STATUS_MAP, TYPE_MAP

# 列序与 product_row_to_dict 下标绑定，改动需同步
BASE_SELECT = """
    SELECT p.id, p.name, p.price, p.description, p.seller, p.status, p.contact,
           p.sold_status, p.sold_time, p.created_at, p.type, p.desc_image,
           p.contact_image, u.nickname AS seller_nickname, p.tags
    FROM products p
    LEFT JOIN users u ON p.seller = u.username
"""


def fetch_products_page(db_config, where, params, per_page, offset):
    """分页查询，返回 (total, rows)；where 中可用别名 p。"""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM products p WHERE {where}", params)
            total = cursor.fetchone()[0]
            cursor.execute(
                f"{BASE_SELECT} WHERE {where} ORDER BY p.id DESC LIMIT %s OFFSET %s",
                list(params) + [per_page, offset],
            )
            rows = cursor.fetchall()
        return total, rows
    finally:
        conn.close()


def product_row_to_dict(row, current_username=None, seller_username_display=False):
    # seller_username_display=True：admin 列表习惯看用户名而非昵称
    data = {
        'id': row[0], 'name': row[1], 'price': row[2], 'description': row[3],
        'seller': row[4] if seller_username_display else (row[13] if row[13] else row[4]),
        'seller_username': row[4],
        'status': row[5], 'status_cn': STATUS_MAP.get(row[5], row[5]),
        'contact': row[6] or '', 'sold_status': row[7],
        'sold_status_cn': SOLD_STATUS_MAP.get(row[7], row[7]),
        'sold_time': row[8].strftime('%Y-%m-%d %H:%M') if row[8] else '',
        'created_at': row[9].strftime('%Y-%m-%d %H:%M') if row[9] else '',
        'type': row[10], 'type_cn': TYPE_MAP.get(row[10], '出售'),
        'desc_image': row[11] or '', 'contact_image': row[12] or '',
        'tags': (row[14] or '') if len(row) > 14 else '',
        'is_own': bool(current_username and current_username == row[4]),
    }
    return data
