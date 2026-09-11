import secrets

from flask import request, session

CSRF_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

def init_csrf(app):
    def csrf_token():
        token = session.get('_csrf_token')
        if not token:
            token = secrets.token_urlsafe(32)
            session['_csrf_token'] = token
        return token

    @app.before_request
    def protect_csrf():
        if request.method not in CSRF_METHODS:
            return None

        expected = session.get('_csrf_token')
        provided = (
            request.form.get('_csrf_token')
            or request.headers.get('X-CSRF-Token')
        )
        if (
            not expected
            or not provided
            or not secrets.compare_digest(expected, provided)
        ):
            return '请求已过期，请刷新页面后重试', 400

        return None

    app.jinja_env.globals['csrf_token'] = csrf_token
