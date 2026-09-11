import pymysql


STATUS_LABELS = {
    'pending': '待确认',
    'confirmed': '已确认',
    'cancelled': '已取消',
}


class OrderError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def get_user_orders(db_config, username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT o.id, o.product_id, p.name, p.price, o.buyer, o.seller,
                   o.status, o.created_at, o.contact, o.message, p.id
            FROM orders o
            LEFT JOIN products p ON o.product_id = p.id
            WHERE o.buyer = %s OR o.seller = %s
            ORDER BY o.created_at DESC
            """,
            (username, username),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    orders = []
    for row in rows:
        status = row[6]
        orders.append(
            {
                'id': row[0],
                'product_id': row[1],
                'product_name': row[2] or '商品已删除',
                'price': float(row[3]) if row[3] is not None else 0.0,
                'buyer': row[4],
                'seller': row[5],
                'status': status,
                'status_label': STATUS_LABELS.get(status, status),
                'created_at': row[7].strftime('%Y-%m-%d %H:%M') if row[7] else '',
                'contact': row[8] or '',
                'message': row[9] or '',
                'product_exists': row[10] is not None,
                'perspective': '买入' if row[4] == username else '卖出',
            }
        )

    return orders


def create_order(db_config, product_id, buyer, contact='', message=''):
    if not product_id:
        raise OrderError('请选择商品')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, seller, status, sold_status
            FROM products
            WHERE id=%s
            FOR UPDATE
            """,
            (product_id,),
        )
        product = cursor.fetchone()

        if not product or product[2] != 'approved' or product[3] != 'unsold':
            raise OrderError('商品不可购买')

        if product[1] == buyer:
            raise OrderError('不能购买自己的商品')

        cursor.execute(
            """
            SELECT id
            FROM orders
            WHERE product_id=%s AND buyer=%s AND status IN ('pending', 'confirmed')
            """,
            (product_id, buyer),
        )
        if cursor.fetchone():
            raise OrderError('您已对该商品下过订单')

        cursor.execute(
            """
            INSERT INTO orders (product_id, buyer, seller, status, contact, message)
            VALUES (%s, %s, %s, 'pending', %s, %s)
            """,
            (product_id, buyer, product[1], contact or '', message or ''),
        )
        order_id = cursor.lastrowid

        cursor.execute(
            """
            UPDATE products
            SET sold_status='sold', sold_time=NOW()
            WHERE id=%s AND sold_status='unsold'
            """,
            (product_id,),
        )
        if cursor.rowcount != 1:
            raise OrderError('商品状态已变化，请刷新后重试')

        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def confirm_order(db_config, order_id, username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT product_id, buyer, seller, status
            FROM orders
            WHERE id=%s
            FOR UPDATE
            """,
            (order_id,),
        )
        order = cursor.fetchone()

        if not order:
            raise OrderError('订单不存在', 404)
        if order[2] != username:
            raise OrderError('只有卖家可以确认订单', 403)
        if order[3] != 'pending':
            raise OrderError('订单状态不正确')

        cursor.execute(
            "UPDATE orders SET status='confirmed', updated_at=NOW() WHERE id=%s",
            (order_id,),
        )
        conn.commit()
        return order[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def cancel_order(db_config, order_id, username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT product_id, buyer, seller, status
            FROM orders
            WHERE id=%s
            FOR UPDATE
            """,
            (order_id,),
        )
        order = cursor.fetchone()

        if not order:
            raise OrderError('订单不存在', 404)
        if username not in (order[1], order[2]):
            raise OrderError('无权限', 403)
        if order[3] in ('cancelled', 'confirmed'):
            raise OrderError('订单状态不正确')

        cursor.execute(
            "UPDATE orders SET status='cancelled', updated_at=NOW() WHERE id=%s",
            (order_id,),
        )
        cursor.execute(
            "UPDATE products SET sold_status='unsold', sold_time=NULL WHERE id=%s",
            (order[0],),
        )
        conn.commit()
        return order[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
