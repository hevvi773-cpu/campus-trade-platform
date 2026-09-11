from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
import pymysql

from services.message_service import (
    MessageError,
    create_message,
    get_chat_messages,
    get_conversations,
)
from services.notify_service import get_badge_counts, get_nickname
from services.authz import is_muted, is_student_session

def _parse_product_id(raw):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _enrich_product_messages(db_config, messages):
    """给带 product_id 的消息批量补价格/图片，用于渲染商品卡片。"""
    product_ids = {m['product_id'] for m in messages if m.get('product_id')}
    if not product_ids:
        return
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            fmt = ','.join(['%s'] * len(product_ids))
            cursor.execute(
                f"SELECT id, price, desc_image, sold_status FROM products WHERE id IN ({fmt})",
                list(product_ids),
            )
            info = {row[0]: {'price': row[1], 'desc_image': row[2], 'sold_status': row[3]} for row in cursor.fetchall()}
    finally:
        conn.close()
    for m in messages:
        pid = m.get('product_id')
        if pid and pid in info:
            m['product_price'] = float(info[pid]['price']) if info[pid]['price'] is not None else None
            m['product_image'] = info[pid]['desc_image'] or ''
            m['product_sold'] = (info[pid]['sold_status'] == 'sold')
        elif pid:
            # 商品已删
            m['product_price'] = None
            m['product_image'] = ''
            m['product_sold'] = False


def _seed_product_card_if_absent(db_config, sender, receiver, product_id):
    """会话内尚无该商品卡片时，落一条带 product_id 的占位消息。"""
    if sender == receiver:
        return

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM messages
                WHERE ((sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s))
                  AND product_id=%s
                """,
                (sender, receiver, receiver, sender, product_id),
            )
            if cursor.fetchone()[0] > 0:
                return  # 已存在相同商品卡片，不再重复

            # 商品存在性校验（避免指向已删商品）
            cursor.execute("SELECT name FROM products WHERE id=%s", (product_id,))
            row = cursor.fetchone()
            if not row:
                return  # 商品已删，静默跳过
            product_name = row[0]

            cursor.execute(
                "INSERT INTO messages (sender, receiver, content, product_id) "
                "VALUES (%s, %s, %s, %s)",
                (
                    sender,
                    receiver,
                    f'我对你的商品「{product_name}」感兴趣，可以聊聊吗？',
                    product_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()

def _user_exists(db_config, username):
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM users WHERE username=%s", (username,))
            return cursor.fetchone() is not None
    finally:
        conn.close()


def _has_conversation(db_config, user_a, user_b):
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM messages WHERE "
                "(sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s) LIMIT 1",
                (user_a, user_b, user_b, user_a),
            )
            return cursor.fetchone() is not None
    finally:
        conn.close()


def create_messages_blueprint(db_config, log_action):
    blueprint = Blueprint('messages', __name__)

    @blueprint.route('/messages')
    def messages_list():
        if not is_student_session():
            return redirect(url_for('login_page'))

        username = session['username']
        conversations = get_conversations(db_config, username)
        return render_template(
            'messages/index.html',
            conversations=conversations,
            badges=get_badge_counts(db_config, username),
        )

    @blueprint.route('/messages/<receiver>')
    def chat_detail(receiver):
        if not is_student_session():
            return redirect(url_for('login_page'))

        # 被禁言用户不能进入聊天
        if is_muted(db_config):
            return render_template('errors/banned.html')

        username = session['username']

        # 越权校验：不能和自己聊；对方须存在；无历史消息且未从商品页进入则 403
        if receiver == username:
            return '不能和自己聊天', 403
        if not _user_exists(db_config, receiver):
            return '对话用户不存在', 404

        product_id_in = _parse_product_id(request.args.get('product_id'))
        if not product_id_in and not _has_conversation(db_config, username, receiver):
            return '无权访问该对话', 403

        # 从商品页进入（带 product_id）且会话内无同款卡片时，自动落一条商品消息
        if product_id_in and receiver != username:
            try:
                _seed_product_card_if_absent(db_config, username, receiver, product_id_in)
            except MessageError:
                # 落消息失败不阻塞进入聊天（兜底）
                pass

        try:
            messages = get_chat_messages(db_config, username, receiver)
        except MessageError as exc:
            return str(exc), exc.status_code

        # 给带 product_id 的消息补上商品价格、图片（模板用于渲染居中商品卡片）
        _enrich_product_messages(db_config, messages)

        return render_template(
            'messages/detail.html',
            receiver=receiver,
            receiver_nickname=get_nickname(db_config, receiver),
            messages=messages,
            current_user=username,
            badges=get_badge_counts(db_config, username),
        )

    @blueprint.route('/send_message', methods=['POST'])
    def send_message():
        if not is_student_session():
            return jsonify({'code': 403, 'msg': '未登录'}), 403

        # 被禁言用户不能发消息
        if is_muted(db_config):
            return jsonify({'code': 403, 'msg': '您已被禁言，无法发送消息'}), 403

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'code': 400, 'msg': '无效请求'}), 400

        receiver = data.get('receiver')
        product_id = _parse_product_id(data.get('product_id'))

        # 同对话页的越权校验
        if not receiver or receiver == session['username']:
            return jsonify({'code': 403, 'msg': '无效的聊天对象'}), 403
        if not _user_exists(db_config, receiver):
            return jsonify({'code': 404, 'msg': '对话用户不存在'}), 404
        if not product_id and not _has_conversation(db_config, session['username'], receiver):
            return jsonify({'code': 403, 'msg': '无权发起该对话'}), 403

        try:
            message_id = create_message(
                db_config,
                session['username'],
                receiver,
                data.get('content'),
                product_id,
            )
        except MessageError as exc:
            return jsonify({'code': exc.status_code, 'msg': str(exc)}), exc.status_code

        log_action('send_message', 'message', message_id, f'to:{receiver}')
        # message_id 前端未使用，不随响应返回（仍写入审计日志）
        return jsonify({'code': 0, 'msg': '发送成功'})

    return blueprint
