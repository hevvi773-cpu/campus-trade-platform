"""权限与角色判断工具。

三级用户：
- 游客（guest）：未登录，只能看首页/详情，不能私聊/收藏/购买/发布。
- 被禁言用户（muted）：已登录但 ban_until > now，可见个人中心但不能发消息/发商品/私聊/收藏/购买。
- 正常用户（student）：啥都行。
- 管理员（admin）：运营权限。

装饰器：
- require_login —— 未登录跳转登录页
- require_not_muted —— 禁言中跳转禁言页/返回 403
- admin_required —— 复用既有定义（仅作 re-export）
- user_kind(db_config) —— 返回当前用户角色字符串，用于模板按角色渲染

设计上：装饰器与具体 Flask app 解耦，不直接 import 全局 app，
避免 routes 与 app_v3 的循环 import。调用方传 db_config 进来。
"""
from datetime import datetime
from functools import wraps

from flask import redirect, render_template, session, url_for

import pymysql


def admin_required(f):
    """管理员权限：与既有实现保持一致（session.identity != 'admin' 返回 403）。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('identity') != 'admin':
            return "无管理员权限", 403
        return f(*args, **kwargs)
    return decorated_function


def require_login(f):
    """未登录则跳登录页。仅要求登录，不要求 student 身份（管理员也能进）。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def require_student(f):
    """必须是已登录的 student（管理员也走不进，会跳登录页）。
    与既有 require_student 一致。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session.get('identity') != 'student':
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def is_student_session():
    """当前会话是否为已登录学生（各蓝图共用的 if 判断）。"""
    return 'username' in session and session.get('identity') == 'student'


def get_user_kind(db_config):
    """返回当前用户角色：'admin' / 'student' / 'guest'。
    注意：本函数不查 ban_until，ban 信息由 user_ban_state 单独提供。
    """
    if 'username' not in session:
        return 'guest'
    role = session.get('identity')
    if role in ('admin', 'student'):
        return role
    return 'guest'


def get_user_ban_state(db_config):
    """检查当前登录 student 是否在 ban_until 期间被禁言。
    返回 dict: {'banned': bool, 'until': datetime|None, 'reason': str|None}
    未登录或非 student 一律返回 not banned。
    """
    if session.get('identity') != 'student' or 'username' not in session:
        return {'banned': False, 'until': None, 'reason': None}

    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ban_until FROM users WHERE username=%s",
            (session.get('username'),),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception:
        return {'banned': False, 'until': None, 'reason': None}

    ban_until = row[0] if row else None
    if ban_until and ban_until > datetime.now():
        return {'banned': True, 'until': ban_until, 'reason': '您当前处于禁言期，相关操作已停用'}
    return {'banned': False, 'until': None, 'reason': None}


def is_muted(db_config):
    """便捷判断：当前登录用户是否被禁言。"""
    return get_user_ban_state(db_config)['banned']


def require_not_muted(db_config, render_banned_template=True):
    """返回一个装饰器：被禁言用户访问时返回 403 或渲染禁言页。
    render_banned_template=True 时渲染 errors/banned.html（与既有 publish 行为一致），
    否则返回纯文本 403（与既有 add_product 行为一致）。
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session or session.get('identity') != 'student':
                return redirect(url_for('login_page'))
            if is_muted(db_config):
                if render_banned_template:
                    return render_template('errors/banned.html')
                return "您已被禁言", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
