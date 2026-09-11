"""管理后台路由。统计查询合并：商品统计 3 次、日指标 4 次 GROUP BY（原 35 次循环）。"""
import os
from datetime import datetime, timedelta

import pymysql
from flask import redirect, render_template, request, session, url_for

from app_v3 import (
    app,
    auto_approve_stale,
    db_config,
    log_action,
    log_search,
)
from services.authz import admin_required
from services.feedback_service import get_all_feedbacks
from services.product_service import fetch_products_page, product_row_to_dict

PER_PAGE = 10


def _build_product_where(q, status_filter):
    where = "1=1"
    params = []
    if q:
        where += " AND (p.name LIKE %s OR p.description LIKE %s)"
        params.extend([f'%{q}%', f'%{q}%'])
    if status_filter:
        where += " AND p.status = %s"
        params.append(status_filter)
    return where, params


def _get_overview_stats(cursor):
    cursor.execute("""
        SELECT COUNT(*),
               IFNULL(SUM(status='pending'),0),
               IFNULL(SUM(status='approved'),0),
               IFNULL(SUM(sold_status='sold'),0)
        FROM products
    """)
    total_count, pending_count, approved_count, sold_count = cursor.fetchone()

    cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
    role_counts = {r[0]: r[1] for r in cursor.fetchall()}
    student_count = role_counts.get('student', 0)
    admin_count = role_counts.get('admin', 0)

    today = datetime.now().replace(hour=0, minute=0, second=0)
    cursor.execute("SELECT COUNT(*) FROM products WHERE created_at >= %s", (today,))
    today_new = cursor.fetchone()[0]

    return {
        'total_count': total_count or 0,
        'pending_count': pending_count or 0,
        'approved_count': approved_count or 0,
        'sold_count': sold_count or 0,
        'student_count': student_count,
        'admin_count': admin_count,
        'user_count': student_count + admin_count,
        'today_new': today_new,
    }


def _get_daily_metrics(cursor):
    start_day = (datetime.now() - timedelta(days=6)).replace(hour=0, minute=0, second=0)

    def _daily_map(sql):
        cursor.execute(sql, (start_day,))
        return {r[0]: r[1] for r in cursor.fetchall()}

    pub_map = _daily_map(
        "SELECT DATE(created_at), COUNT(*) FROM products WHERE created_at >= %s GROUP BY DATE(created_at)")
    amount_map = _daily_map(
        "SELECT DATE(sold_time), IFNULL(SUM(price),0) FROM products "
        "WHERE sold_status='sold' AND sold_time >= %s GROUP BY DATE(sold_time)")
    reg_map = _daily_map(
        "SELECT DATE(created_at), COUNT(*) FROM users WHERE created_at >= %s GROUP BY DATE(created_at)")
    eval_map = _daily_map(
        "SELECT DATE(created_at), COUNT(*) FROM evaluations WHERE created_at >= %s GROUP BY DATE(created_at)")

    date_labels, daily_counts, daily_amounts, daily_regs, active_days = [], [], [], [], []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        label = day.strftime('%m-%d')
        pub = pub_map.get(day, 0)
        reg = reg_map.get(day, 0)
        ev = eval_map.get(day, 0)
        date_labels.append(label)
        daily_counts.append(pub)
        daily_amounts.append(float(amount_map.get(day, 0)))
        daily_regs.append(reg)
        active_days.append({'date': label, 'reg': reg, 'pub': pub, 'eval': ev})
    return date_labels, daily_counts, daily_amounts, daily_regs, active_days


def _get_top_sellers(cursor):
    cursor.execute("""
        SELECT seller, COUNT(*) AS cnt, IFNULL(SUM(price),0) AS total
        FROM products
        WHERE sold_status='sold'
        GROUP BY seller
        ORDER BY total DESC
        LIMIT 5
    """)
    return [
        {'seller': r[0], 'total_count': r[1], 'total_amount': float(r[2])}
        for r in cursor.fetchall()
    ]


@app.route('/admin')
@admin_required
def admin_panel():
    auto_approve_stale()

    q = request.args.get('q', '').strip()
    if q:
        log_search(q)

    # 状态 Tab 筛选：待审核 / 已上架 / 已驳回
    status_filter = request.args.get('status', '').strip()
    if status_filter not in ('pending', 'approved', 'rejected'):
        status_filter = ''

    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE

    where, params = _build_product_where(q, status_filter)
    total, rows = fetch_products_page(db_config, where, params, PER_PAGE, offset)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    products = [
        product_row_to_dict(r, seller_username_display=True)
        for r in rows
    ]

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, nickname, role, DATE_FORMAT(ban_until, '%%Y-%%m-%%d %%H:%%i'), student_id FROM users"
    )
    users = cursor.fetchall()
    stats = _get_overview_stats(cursor)
    date_labels, daily_counts, daily_amounts, daily_regs, active_days = _get_daily_metrics(cursor)
    top_users = _get_top_sellers(cursor)
    cursor.close()
    conn.close()

    feedbacks = get_all_feedbacks(db_config)
    current_user = session.get('nickname', session.get('username', '管理员'))

    return render_template(
        'admin/index.html',
        products=products, users=users, current_user=current_user,
        total_count=stats['total_count'], pending_count=stats['pending_count'],
        approved_count=stats['approved_count'], sold_count=stats['sold_count'],
        user_count=stats['user_count'], student_count=stats['student_count'],
        admin_count=stats['admin_count'],
        today_new=stats['today_new'], q=q, page=page, total_pages=total_pages,
        status_filter=status_filter,
        date_labels=date_labels, daily_counts=daily_counts,
        daily_amounts=daily_amounts, daily_regs=daily_regs,
        active_days=active_days, top_users=top_users, feedbacks=feedbacks,
    )


@app.route('/approve/<int:pid>', methods=['POST'])
@admin_required
def approve(pid):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET status='approved' WHERE id=%s", (pid,))
    log_action('approve_product', 'product', pid)
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/reject/<int:pid>', methods=['POST'])
@admin_required
def reject(pid):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET status='rejected' WHERE id=%s", (pid,))
    log_action('reject_product', 'product', pid)
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/delete/<int:pid>', methods=['POST'])
def delete(pid):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT seller, status, desc_image, contact_image FROM products WHERE id=%s",
        (pid,),
    )
    product = cursor.fetchone()
    if not product:
        cursor.close()
        conn.close()
        return redirect('/')
    seller, status, desc_img, contact_img = product
    can_delete = False
    if session.get('identity') == 'admin':
        can_delete = True
    elif session.get('identity') == 'student' and session.get('username') == seller:
        # 卖家本人可删任何状态的商品
        can_delete = True
    if not can_delete:
        cursor.close()
        conn.close()
        return "无权限", 403

    for img in [desc_img, contact_img]:
        if img and os.path.exists(img):
            try:
                os.remove(img)
            except Exception:
                pass
    cursor.execute("DELETE FROM products WHERE id=%s", (pid,))
    log_action('delete_product', 'product', pid, f'status:{status}')
    conn.commit()
    cursor.close()
    conn.close()

    # next 仅允许站内相对路径，防开放重定向
    next_url = request.form.get('next', '')
    if next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    destination = 'admin_panel' if session.get('identity') == 'admin' else 'index'
    return redirect(url_for(destination))


@app.route('/ban_user/<username>', methods=['POST'])
@admin_required
def ban_user(username):
    if username == 'admin':
        return "不能禁言管理员", 403
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    ban_time = datetime.now() + timedelta(days=7)
    cursor.execute(
        "UPDATE users SET ban_until=%s WHERE username=%s",
        (ban_time, username),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/unban_user/<username>', methods=['POST'])
@admin_required
def unban_user(username):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET ban_until=NULL WHERE username=%s", (username,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/delete_user/<username>', methods=['POST'])
@admin_required
def delete_user(username):
    if username == 'admin':
        return "不能删除管理员", 403
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT desc_image, contact_image FROM products WHERE seller=%s", (username,))
    images = cursor.fetchall()
    for desc_img, contact_img in images:
        for img in [desc_img, contact_img]:
            if img and os.path.exists(img):
                try:
                    os.remove(img)
                except Exception:
                    pass
    cursor.execute("DELETE FROM products WHERE seller=%s", (username,))
    cursor.execute("DELETE FROM users WHERE username=%s", (username,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/approve_all', methods=['POST'])
@admin_required
def approve_all():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET status='approved' WHERE status='pending'")
    affected = cursor.rowcount
    log_action('approve_all', 'product', None, f'通过{affected}件')
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/ban_all', methods=['POST'])
@admin_required
def ban_all():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    ban_time = datetime.now() + timedelta(days=7)
    cursor.execute(
        "UPDATE users SET ban_until=%s WHERE role='student' AND ban_until IS NULL",
        (ban_time,),
    )
    affected = cursor.rowcount
    log_action('ban_all', 'user', None, f'禁言{affected}人')
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/unban_all', methods=['POST'])
@admin_required
def unban_all():
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET ban_until=NULL WHERE ban_until IS NOT NULL")
    affected = cursor.rowcount
    log_action('unban_all', 'user', None, f'解除{affected}人')
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))
