"""认证路由：登录、注册、登出、填写学号（选填）。"""
import re
import threading
import time

import pymysql
from flask import redirect, render_template, request, session, url_for

from app_v3 import app, db_config, log_login
from services.auth_service import AuthError, authenticate_user, register_student
from services.authz import require_student

# 登录限流：同「用户名+IP」连续失败 5 次锁 10 分钟；内存计数按 worker 进程独立，重启清零
_LOGIN_FAILS = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_MAX_FAILS = 5
_LOGIN_LOCK_SECONDS = 600


def _login_key(username):
    return f"{(username or '').strip().lower()}|{request.remote_addr or ''}"


def _locked_remaining_seconds(key):
    now = time.time()
    with _LOGIN_LOCK:
        fails, lock_until = _LOGIN_FAILS.get(key, (0, 0))
        if lock_until and lock_until > now:
            return int(lock_until - now)
        if lock_until and lock_until <= now:
            _LOGIN_FAILS.pop(key, None)
    return 0


def _record_login_fail(key):
    with _LOGIN_LOCK:
        fails, _ = _LOGIN_FAILS.get(key, (0, 0))
        fails += 1
        lock_until = time.time() + _LOGIN_LOCK_SECONDS if fails >= _LOGIN_MAX_FAILS else 0
        _LOGIN_FAILS[key] = (fails, lock_until)
    return max(_LOGIN_MAX_FAILS - fails, 0)


def _clear_login_fails(key):
    with _LOGIN_LOCK:
        _LOGIN_FAILS.pop(key, None)


@app.route('/login_page')
def login_page():
    return render_template('auth/login.html', error=None, msg=None)


@app.route('/do_login', methods=['POST'])
def do_login():
    key = _login_key(request.form.get('username'))
    locked_for = _locked_remaining_seconds(key)
    if locked_for:
        minutes = (locked_for + 59) // 60
        return render_template(
            'auth/login.html',
            error=f'失败次数过多，账号已临时锁定，请约 {minutes} 分钟后再试',
            msg=None,
        )

    user = authenticate_user(
        db_config,
        request.form.get('username'),
        request.form.get('password'),
    )
    if user:
        _clear_login_fails(key)
        session['username'] = user['username']
        session['identity'] = user['role']
        session['nickname'] = user['nickname']
        log_login(user['username'])
        if user['role'] == 'admin':
            return redirect('/admin')
        return redirect('/')

    remaining = _record_login_fail(key)
    if remaining <= 0:
        error = '失败次数过多，账号已临时锁定 10 分钟'
    else:
        error = f'用户名或密码错误（剩余尝试次数：{remaining}）'
    return render_template('auth/login.html', error=error, msg=None)


@app.route('/do_register', methods=['POST'])
def do_register():
    try:
        msg = register_student(
            db_config,
            request.form.get('username'),
            request.form.get('password'),
            request.form.get('confirm_password'),
            request.form.get('nickname'),
        )
    except AuthError as exc:
        return render_template('auth/login.html', error=str(exc), msg=None)
    return render_template('auth/login.html', error=None, msg=msg)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/fill_student_id', methods=['GET', 'POST'])
@require_student
def fill_student_id():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        if not student_id or not re.match(r'^20\d{13}$', student_id):
            return render_template('auth/fill_student_id.html', error='学号格式错误，须为15位数字且以20开头')

        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE student_id=%s AND username!=%s",
            (student_id, session['username']),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return render_template('auth/fill_student_id.html', error='该学号已被其他账号使用')
        cursor.execute(
            "UPDATE users SET student_id=%s WHERE username=%s",
            (student_id, session['username']),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/')
    return render_template('auth/fill_student_id.html', error=None)
