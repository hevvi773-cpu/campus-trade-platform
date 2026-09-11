"""首页路由：列表/搜索/标签/分页/加载更多。查询逻辑在 services.product_service。"""
from flask import jsonify, redirect, render_template, request, session

from app_v3 import (
    app,
    auto_approve_stale,
    db_config,
    get_badge_counts,
    get_user_favorite_ids,
    log_search,
    PRODUCT_TAGS,
)
from services.authz import get_user_ban_state
from services.product_service import (
    fetch_products_page,
    product_row_to_dict,
)

PER_PAGE = 10


def _build_visibility_where(current_username, q, tag, is_filtering):
    # 默认首页：已过审 + 自己的待审核；搜索/标签筛选：仅已过审
    where = "p.status='approved'"
    params = []

    if current_username and not is_filtering:
        where = "(p.status='approved' OR (p.seller = %s AND p.status = 'pending'))"
        params.append(current_username)

    # 标签条件须在 OR 分组之外，否则本人商品会绕过标签筛选
    if tag:
        where += " AND FIND_IN_SET(%s, p.tags)"
        params.append(tag)

    if q:
        where += " AND (p.name LIKE %s OR p.description LIKE %s)"
        params.extend([f'%{q}%', f'%{q}%'])

    return where, params


def _rows_to_products(rows, current_username):
    return [product_row_to_dict(row, current_username=current_username) for row in rows]


def _current_ban_until_text():
    if session.get('identity') != 'student':
        return None
    state = get_user_ban_state(db_config)
    if state['banned'] and state['until']:
        return state['until'].strftime('%Y-%m-%d %H:%M')
    return None


@app.route('/')
def index():
    if session.get('identity') == 'admin':
        return redirect('/admin')

    auto_approve_stale()

    current_identity = session.get('identity', 'guest')
    current_user = session.get('nickname', session.get('username', '游客'))
    current_username = session.get('username')

    q = request.args.get('q', '').strip()
    if q:
        log_search(q)

    tag = request.args.get('tag', '').strip()
    if tag not in PRODUCT_TAGS:
        tag = ''

    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * PER_PAGE

    is_filtering = bool(q or tag)
    where, params = _build_visibility_where(current_username, q, tag, is_filtering)

    total, rows = fetch_products_page(db_config, where, params, PER_PAGE, offset)
    products = _rows_to_products(rows, current_username)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE

    sell_products = [p for p in products if p['type'] == 1 and p['sold_status'] != 'sold']
    buy_products = [p for p in products if p['type'] == 0 and p['sold_status'] != 'sold']
    sold_products = [p for p in products if p['sold_status'] == 'sold']

    ban_until = _current_ban_until_text()
    fav_ids = get_user_favorite_ids(db_config, current_username)
    badges = get_badge_counts(db_config, current_username)
    has_more = page < total_pages

    # 加载更多：Ajax 返回三个分组的卡片 HTML 片段
    if request.args.get('ajax') == '1':
        def _render_cards(group_products, kind):
            return render_template(
                'home/_cards_ajax.html',
                products=group_products, kind=kind,
                fav_ids=fav_ids, current_identity=current_identity,
                ban_until=ban_until,
            )

        return jsonify({
            'sell': _render_cards(sell_products, 'sell'),
            'buy': _render_cards(buy_products, 'buy'),
            'sold': _render_cards(sold_products, 'sold'),
            'has_more': has_more,
        })

    return render_template(
        'home/index.html',
        current_identity=current_identity,
        badges=badges,
        current_user=current_user,
        ban_until=ban_until,
        q=q, page=page,
        has_more=has_more,
        sell_products=sell_products,
        buy_products=buy_products,
        sold_products=sold_products,
        fav_ids=fav_ids, tag=tag, all_tags=PRODUCT_TAGS,
    )
