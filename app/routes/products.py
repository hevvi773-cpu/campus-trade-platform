"""商品相关路由：发布、添加、标记已售、评价、详情 API。"""
import os
from datetime import datetime

import pymysql
from flask import current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from app_v3 import (
    app,
    allowed_file,
    db_config,
    log_action,
    log_view,
    PRODUCT_TAGS,
    SOLD_STATUS_MAP,
    STATUS_MAP,
    TYPE_MAP,
)
from services.authz import is_muted, require_not_muted


@app.route('/publish')
@require_not_muted(db_config, render_banned_template=True)
def publish_page():
    return render_template('products/publish.html', all_tags=PRODUCT_TAGS)


@app.route('/add', methods=['POST'])
@require_not_muted(db_config, render_banned_template=False)
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    desc = request.form.get('description')
    contact = request.form.get('contact')
    type_val = request.form.get('type')
    seller = session['username']

    desc_image = ''
    if 'desc_image' in request.files:
        file = request.files['desc_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            desc_image = 'static/uploads/desc/' + timestamp + filename
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], 'desc', timestamp + filename))

    contact_image = ''
    if 'contact_image' in request.files:
        file = request.files['contact_image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            contact_image = 'static/uploads/contact/' + timestamp + filename
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], 'contact', timestamp + filename))

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    sql = """INSERT INTO products(name, price, description, seller, status, contact, sold_status, type, desc_image, contact_image, tags)
             VALUES(%s, %s, %s, %s, 'pending', %s, 'unsold', %s, %s, %s, %s)"""
    tag_list = [t for t in request.form.getlist('tags') if t in PRODUCT_TAGS]
    tags_str = ','.join(dict.fromkeys(tag_list))
    cursor.execute(sql, (name, price, desc, seller, contact, type_val, desc_image, contact_image, tags_str))
    conn.commit()
    cursor.close()
    conn.close()
    flash('发布成功，等待审核')
    return redirect('/')


@app.route('/mark_sold/<int:pid>', methods=['POST'])
def mark_sold(pid):
    if 'username' not in session:
        return redirect('/login_page')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT seller, status FROM products WHERE id=%s", (pid,))
    product = cursor.fetchone()
    if not product:
        cursor.close()
        conn.close()
        return redirect('/')

    seller, status = product
    if session.get('identity') == 'student' and session.get('username') == seller and status == 'approved':
        cursor.execute(
            "UPDATE products SET sold_status='sold', sold_time=NOW() WHERE id=%s",
            (pid,),
        )
        log_action('mark_sold', 'product', pid)
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/')

    cursor.close()
    conn.close()
    return "无权限", 403


@app.route('/evaluate/<int:pid>', methods=['GET', 'POST'])
def evaluate(pid):
    if 'username' not in session or session.get('identity') != 'student':
        return redirect('/login_page')

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.seller, p.sold_status, p.name, u.nickname
        FROM products p
        LEFT JOIN users u ON p.seller = u.username
        WHERE p.id=%s
    """, (pid,))
    product = cursor.fetchone()
    if not product:
        cursor.close()
        conn.close()
        return "商品不存在", 404

    cursor.execute(
        "SELECT id FROM orders WHERE product_id=%s AND buyer=%s AND status='confirmed'",
        (pid, session["username"]),
    )
    has_order = cursor.fetchone()

    if not has_order and not (session["username"] == product[0] and product[1] == 'sold'):
        cursor.close()
        conn.close()
        return "您尚未完成该商品的交易，无法评价", 403

    seller_username, sold_status, product_name, seller_nickname = product

    if session['username'] == seller_username:
        cursor.close()
        conn.close()
        return "不能评价自己的商品", 403

    cursor.execute(
        "SELECT id FROM evaluations WHERE product_id=%s AND from_user=%s",
        (pid, session['username']),
    )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return "您已评价过该商品", 403

    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        content = request.form.get('content', '')
        if not rating or rating < 1 or rating > 5:
            cursor.close()
            conn.close()
            return render_template(
                'products/evaluate.html',
                error='评分须为1~5',
                product=(product_name, seller_nickname or seller_username),
                pid=pid,
            )
        cursor.execute(
            "INSERT INTO evaluations (product_id, from_user, to_user, rating, content) VALUES (%s, %s, %s, %s, %s)",
            (pid, session['username'], seller_username, rating, content),
        )
        conn.commit()
        cursor.close()
        conn.close()
        log_action('evaluate', 'product', pid, f'rating:{rating} to:{seller_username}')
        return redirect('/')

    cursor.close()
    conn.close()
    return render_template(
        'products/evaluate.html',
        error=None,
        product=(product_name, seller_nickname or seller_username),
        pid=pid,
    )


@app.route('/api/product/<int:pid>')
def api_product_detail(pid):
    # 详情 API 限制：游客/被禁言不能调用（与"不能查看详情"一致）
    if 'username' not in session or session.get('identity') not in ('student', 'admin'):
        return {'code': 403, 'msg': '请先登录'}
    if session.get('identity') == 'student' and is_muted(db_config):
        return {'code': 403, 'msg': '您已被禁言'}

    log_view(pid)

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.price, p.description, p.seller, p.status, p.contact,
               p.sold_status, p.sold_time, p.created_at, p.type, p.desc_image,
               p.contact_image,
               u.nickname as seller_nickname,
               e.rating, e.content, e.from_user, e.created_at AS eval_time, p.tags
        FROM products p
        LEFT JOIN users u ON p.seller = u.username
        LEFT JOIN evaluations e ON p.id = e.product_id
        WHERE p.id=%s
    """, (pid,))
    p = cursor.fetchone()
    cursor.close()
    conn.close()

    if not p:
        return {'code': 404, 'msg': '商品不存在'}

    seller_display = p[13] if p[13] else p[4]
    is_seller = (session.get('username') == p[4])
    data = {
        'name': p[1], 'price': float(p[2]), 'description': p[3] or '',
        'seller': seller_display,
        'seller_username': p[4],
        'status_text': STATUS_MAP.get(p[5], p[5]),
        'contact': p[6] or '', 'sold_status': p[7], 'sold_status_text': SOLD_STATUS_MAP.get(p[7], p[7]),
        'sold_time': p[8].strftime('%Y-%m-%d %H:%M') if p[8] else '',
        'created_at': p[9].strftime('%Y-%m-%d %H:%M') if p[9] else '',
        'type': p[10], 'type_text': TYPE_MAP.get(p[10], '出售'),
        'desc_image': p[11] or '', 'contact_image': p[12] or '',
        'is_seller': is_seller,
        'evaluation': {
            'rating': p[14] if p[14] is not None else None,
            'content': p[15] if p[15] else None,
            'from_user': p[16] if p[16] else None,
            'created_at': p[17].strftime('%Y-%m-%d %H:%M') if p[17] else None,
        } if p[14] is not None else None,
        'tags': (p[18] or '') if len(p) > 18 else '',
    }
    return {'code': 0, 'data': data}
