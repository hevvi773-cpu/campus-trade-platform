"""个人中心路由：只做登录校验和渲染，数据在 services.profile_service。"""
from flask import redirect, render_template, session

from app_v3 import app, db_config
from services.profile_service import load_profile_data


@app.route('/profile')
def profile():
    if 'username' not in session or session.get('identity') != 'student':
        return redirect('/login_page')

    data = load_profile_data(db_config, session['username'])
    if data is None:
        # 账号已被注销：清会话回登录页
        session.clear()
        return redirect('/login_page')

    return render_template('profile/index.html', **data)
