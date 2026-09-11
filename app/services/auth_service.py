import re

import pymysql
from werkzeug.security import check_password_hash, generate_password_hash


class AuthError(Exception):
    """Raised when a login or registration request is invalid."""


def clean_text(value):
    return (value or '').strip()


def validate_username(username):
    username = clean_text(username)

    if len(username) < 3 or len(username) > 50:
        raise AuthError("用户名长度需在3-50个字符之间")

    if not re.fullmatch(r'[a-zA-Z0-9_]+', username):
        raise AuthError("用户名只能包含字母、数字和下划线")

    return username


def hash_password(password):
    return generate_password_hash(password)


def authenticate_user(db_config, username, password):
    username = clean_text(username)
    password = password or ''

    if not username or not password:
        return None

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT username, password, role, nickname, student_id FROM users WHERE username=%s",
            (username,),
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user or not check_password_hash(user[1], password):
        return None

    return {
        'username': user[0],
        'role': user[2],
        'nickname': user[3] or user[0],
        'student_id': user[4],
    }


def register_student(db_config, username, password, confirm_password, nickname):
    username = validate_username(username)
    nickname = clean_text(nickname)
    password = password or ''
    confirm_password = confirm_password or ''

    if not password:
        raise AuthError("用户名和密码不能为空")

    if password != confirm_password:
        raise AuthError("两次密码不一致")

    if not nickname:
        raise AuthError("昵称必须填写")

    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            raise AuthError("该用户名已被注册，请直接登录")

        cursor.execute(
            "INSERT INTO users (username, password, nickname, role) VALUES (%s, %s, %s, 'student')",
            (username, hash_password(password), nickname),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    return f"注册成功！欢迎 {nickname}，请登录"
