from flask import Blueprint, redirect, render_template, request, session, url_for

from services.order_service import (
    OrderError,
    cancel_order as cancel_order_record,
    confirm_order as confirm_order_record,
    create_order as create_order_record,
    get_user_orders,
)
from services.notify_service import get_badge_counts
from services.authz import is_muted, is_student_session

def create_orders_blueprint(db_config, log_action):
    blueprint = Blueprint('orders', __name__)

    @blueprint.route('/orders')
    def my_orders():
        if not is_student_session():
            return redirect(url_for('login_page'))

        username = session['username']
        orders = get_user_orders(db_config, username)
        # 每单算出"该跟谁聊"：我是买家就找卖家，反之亦然
        for order in orders:
            order['peer'] = order['seller'] if order['buyer'] == username else order['buyer']
        return render_template(
            'orders/index.html',
            orders=orders,
            current_user=username,
            badges=get_badge_counts(db_config, username),
        )

    @blueprint.route('/order/create', methods=['POST'])
    def create_order():
        if not is_student_session():
            return redirect(url_for('login_page'))
        if is_muted(db_config):
            return '禁言期间无法下单', 403

        product_id = request.form.get('product_id', type=int)
        try:
            order_id = create_order_record(
                db_config,
                product_id,
                session['username'],
                request.form.get('contact', ''),
                request.form.get('message', ''),
            )
        except OrderError as exc:
            return str(exc), exc.status_code

        log_action('create_order', 'order', order_id, f'product:{product_id}')
        return redirect(url_for('orders.my_orders'))

    @blueprint.route('/order/confirm/<int:order_id>', methods=['POST'])
    def confirm_order(order_id):
        if not is_student_session():
            return redirect(url_for('login_page'))

        try:
            product_id = confirm_order_record(
                db_config,
                order_id,
                session['username'],
            )
        except OrderError as exc:
            return str(exc), exc.status_code

        log_action('confirm_order', 'order', order_id, f'product:{product_id}')
        return redirect(url_for('orders.my_orders'))

    @blueprint.route('/order/cancel/<int:order_id>', methods=['POST'])
    def cancel_order(order_id):
        if not is_student_session():
            return redirect(url_for('login_page'))

        try:
            product_id = cancel_order_record(
                db_config,
                order_id,
                session['username'],
            )
        except OrderError as exc:
            return str(exc), exc.status_code

        log_action('cancel_order', 'order', order_id, f'product:{product_id}')
        return redirect(url_for('orders.my_orders'))

    return blueprint
