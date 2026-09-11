"""收藏路由：切换收藏、我的收藏列表。"""
import pymysql
from flask import redirect, render_template, request, session, url_for

from app_v3 import (
    app,
    connect_db,
    db_config,
    log_action,
    SOLD_STATUS_MAP,
    STATUS_MAP,
)
from services.authz import is_muted


@app.route('/favorite/toggle/<int:pid>', methods=['POST'])
def toggle_favorite(pid):
    """切换收藏状态"""
    if 'username' not in session:
        return redirect('/login_page')

    # 被禁言用户不能收藏
    if is_muted(db_config):
        return render_template('errors/banned.html')

    username = session['username']
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM favorites WHERE username=%s AND product_id=%s",
        (username, pid),
    )
    exists = cursor.fetchone()
    if exists:
        cursor.execute(
            "DELETE FROM favorites WHERE username=%s AND product_id=%s",
            (username, pid),
        )
        action = 'removed'
    else:
        cursor.execute(
            "INSERT INTO favorites (username, product_id) VALUES (%s, %s)",
            (username, pid),
        )
        action = 'added'
    conn.commit()
    log_action('toggle_favorite', 'product', pid, f'action:{action}')
    cursor.close()
    conn.close()
    return redirect(url_for('my_favorites'))


@app.route('/favorites')
def my_favorites():
    """我的收藏列表"""
    if 'username' not in session:
        return redirect('/login_page')

    username = session['username']
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.description, p.seller, p.status, p.sold_status,
               p.created_at, p.type, u.nickname as seller_nickname
        FROM favorites f
        JOIN products p ON f.product_id = p.id
        LEFT JOIN users u ON p.seller = u.username
        WHERE f.username = %s
        ORDER BY f.created_at DESC
    """, (username,))
    favorites_raw = cursor.fetchall()
    cursor.close()
    conn.close()


    favorites = []
    for p in favorites_raw:
        status_cn = STATUS_MAP.get(p[5], p[5])
        sold_status_cn = SOLD_STATUS_MAP.get(p[6], p[6])
        favorites.append({
            'id': p[0], 'name': p[1], 'price': p[2], 'description': p[3],
            'seller': p[4], 'status': status_cn, 'sold_status': sold_status_cn,
            'created_at': str(p[7]) if p[7] else '', 'type': p[8] if len(p) > 8 else 1,
            'seller_nickname': p[9] if len(p) > 9 else p[4],
        })

    current_username = session.get('username')

    return render_template(
        'favorites/index.html',
        current_username=current_username,
        favorites=favorites,
    )
