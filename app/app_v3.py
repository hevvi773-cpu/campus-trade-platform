"""
校园二手交易系统 v2.0
改动：密码加密 | 订单系统 | 收藏功能 | 模块化模板
"""
import os
import re
from datetime import datetime, timedelta
from flask import Flask, request, session
import pymysql
from werkzeug.middleware.proxy_fix import ProxyFix
from csrf import init_csrf
from services.audit_service import record_action, record_login, record_search, record_view
from services.auth_service import hash_password
from services.feedback_service import get_all_feedbacks
from services.notify_service import get_badge_counts, get_user_favorite_ids, mark_feedbacks_read
from routes.feedback import create_feedback_blueprint
from routes.messages import create_messages_blueprint
from routes.orders import create_orders_blueprint

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_local_env():
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)

def env_int(name, default):
    value = os.getenv(name)
    if value in (None, ''):
        return default
    return int(value)

def env_bool(name, default=False):
    value = os.getenv(name)
    if value in (None, ''):
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}

def required_env(name):
    value = os.getenv(name)
    if value in (None, ''):
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value

def validate_db_name(database):
    if not re.fullmatch(r'[A-Za-z0-9_]+', database):
        raise ValueError('Database name must contain only letters, numbers, and underscores.')
    return database

load_local_env()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=required_env('SECONDHAND_SECRET_KEY'),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=env_bool('SECONDHAND_COOKIE_SECURE'),
    AUTO_CREATE_DATABASE=env_bool('SECONDHAND_AUTO_CREATE_DB', True),
)
if env_bool('SECONDHAND_TRUST_PROXY'):
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )
init_csrf(app)

def connect_db(include_database=True):
    config = db_config.copy()
    if not include_database:
        config.pop('database', None)
    return pymysql.connect(**config)

# 图片上传配置

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

MAX_CONTENT_LENGTH = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

os.makedirs(os.path.join(UPLOAD_FOLDER, 'desc'), exist_ok=True)

os.makedirs(os.path.join(UPLOAD_FOLDER, 'contact'), exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def allowed_file(filename):

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 数据库配置

db_config = {

    'host': os.getenv('SECONDHAND_DB_HOST', '127.0.0.1'),

    'port': env_int('SECONDHAND_DB_PORT', 3306),

    'user': os.getenv('SECONDHAND_DB_USER', 'root'),

    'password': required_env('SECONDHAND_DB_PASSWORD'),

    'database': validate_db_name(os.getenv('SECONDHAND_DB_NAME', 'secondhand_db')),

    'charset': 'utf8mb4'

}

def ensure_database():
    conn = connect_db(include_database=False)
    cursor = conn.cursor()
    database = db_config['database']
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    cursor.close()
    conn.close()

# ==================== 日志记录 ====================

def log_action(action, target_type=None, target_id=None, detail=None):
    username = session.get('username', 'guest')
    try:
        record_action(
            db_config,
            username,
            action,
            target_type,
            target_id,
            detail,
        )
    except pymysql.MySQLError:
        app.logger.exception('Failed to record action log')

app.register_blueprint(create_orders_blueprint(db_config, log_action))
app.register_blueprint(create_messages_blueprint(db_config, log_action))
app.register_blueprint(
    create_feedback_blueprint(
        db_config,
        log_action,
        app.config['UPLOAD_FOLDER'],
        allowed_file,
    )
)

def log_login(username):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
    ip = ip.split(',', 1)[0].strip()[:45]
    user_agent = request.headers.get('User-Agent', '')[:500]
    try:
        record_login(db_config, username, ip, user_agent)
    except pymysql.MySQLError:
        app.logger.exception('Failed to record login log')

def log_view(product_id):
    username = session.get('username', 'guest')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr) or ''
    ip = ip.split(',', 1)[0].strip()[:45]
    try:
        record_view(db_config, username, product_id, ip)
    except pymysql.MySQLError:
        app.logger.exception('Failed to record product view')

def log_search(keyword, result_count=0):
    username = session.get('username', 'guest')
    try:
        record_search(db_config, username, keyword, result_count)
    except pymysql.MySQLError:
        app.logger.exception('Failed to record search log')

# 常量统一定义在 services.constants，此处 re-export 保持兼容
from services.constants import (  # noqa: F401
    PRODUCT_TAGS,
    SOLD_STATUS_MAP,
    STATUS_MAP,
    TYPE_MAP,
)

# ==================== 数据库初始化 ====================

def init_db():

    if app.config['AUTO_CREATE_DATABASE']:
        ensure_database()

    conn = connect_db()

    cursor = conn.cursor()

    # 用户表

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS users (

            id INT AUTO_INCREMENT PRIMARY KEY,

            username VARCHAR(100) UNIQUE NOT NULL,

            password VARCHAR(255) NOT NULL,

            nickname VARCHAR(100),

            role VARCHAR(20) DEFAULT 'student',

            ban_until TIMESTAMP NULL DEFAULT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

    ''')

    cursor.execute("SHOW COLUMNS FROM users LIKE 'student_id'")

    if not cursor.fetchone():

        cursor.execute("ALTER TABLE users ADD COLUMN student_id VARCHAR(15) UNIQUE DEFAULT NULL")

    cursor.execute("SHOW COLUMNS FROM users LIKE 'last_login'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME DEFAULT NULL")

    cursor.execute("SHOW COLUMNS FROM users LIKE 'login_count'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE users ADD COLUMN login_count INT NOT NULL DEFAULT 0")

    # 商品表

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS products (

            id INT AUTO_INCREMENT PRIMARY KEY,

            name VARCHAR(200) NOT NULL,

            price DECIMAL(10,2) NOT NULL,

            description TEXT,

            seller VARCHAR(100) NOT NULL,

            status VARCHAR(20) DEFAULT 'pending',

            contact VARCHAR(100) DEFAULT '',

            sold_status VARCHAR(20) DEFAULT 'unsold',

            sold_time TIMESTAMP NULL DEFAULT NULL,

            type TINYINT DEFAULT 1,

            desc_image VARCHAR(200) DEFAULT '',

            contact_image VARCHAR(200) DEFAULT '',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

    ''')

    # 评价表

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS evaluations (

            id INT AUTO_INCREMENT PRIMARY KEY,

            product_id INT NOT NULL,

            from_user VARCHAR(100) NOT NULL,

            to_user VARCHAR(100) NOT NULL,

            rating TINYINT NOT NULL,

            content TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE KEY unique_product (product_id)

        )

    ''')

    # 私信表

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS messages (

            id INT AUTO_INCREMENT PRIMARY KEY,

            sender VARCHAR(100) NOT NULL,

            receiver VARCHAR(100) NOT NULL,

            content TEXT NOT NULL,

            is_read TINYINT(1) DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

    ''')

    # 反馈表（已增加 image 列）

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS feedbacks (

            id INT AUTO_INCREMENT PRIMARY KEY,

            username VARCHAR(100) NOT NULL,

            title VARCHAR(200) NOT NULL,

            content TEXT NOT NULL,

            status ENUM('pending','resolved') DEFAULT 'pending',

            reply TEXT,

            image VARCHAR(200) DEFAULT '',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

        )

    ''')

    cursor.execute("SHOW COLUMNS FROM feedbacks LIKE 'image'")

    if not cursor.fetchone():

        cursor.execute("ALTER TABLE feedbacks ADD COLUMN image VARCHAR(200) DEFAULT ''")

    cursor.execute("SHOW COLUMNS FROM products LIKE 'tags'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE products ADD COLUMN tags VARCHAR(100) DEFAULT ''")

    # 未读角标：反馈的已读标记
    cursor.execute("SHOW COLUMNS FROM feedbacks LIKE 'is_read'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE feedbacks ADD COLUMN is_read TINYINT(1) DEFAULT 0")

    # 消息来源商品：记录对方是从哪个商品点进来的
    cursor.execute("SHOW COLUMNS FROM messages LIKE 'product_id'")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE messages ADD COLUMN product_id INT NULL DEFAULT NULL")

    # 审计日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS action_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            target_type VARCHAR(50) DEFAULT NULL,
            target_id VARCHAR(100) DEFAULT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_action_logs_username_created (username, created_at),
            INDEX idx_action_logs_action_created (action, created_at)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            ip VARCHAR(45) DEFAULT '',
            user_agent VARCHAR(500) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_login_logs_username_created (username, created_at)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS view_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            product_id INT NOT NULL,
            ip VARCHAR(45) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_view_logs_product_created (product_id, created_at),
            INDEX idx_view_logs_username_created (username, created_at)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            keyword VARCHAR(255) NOT NULL,
            result_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_search_logs_username_created (username, created_at)
        )
    ''')

    # 订单表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            buyer VARCHAR(100) NOT NULL,
            seller VARCHAR(100) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            contact VARCHAR(100) DEFAULT '',
            message VARCHAR(500) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    ''')

    # 收藏表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            product_id INT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_user_product (username, product_id),
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')

    # 确保 admin 存在

    cursor.execute("SELECT password FROM users WHERE username='admin'")

    admin_user = cursor.fetchone()

    admin_password = required_env('SECONDHAND_ADMIN_PASSWORD')

    if not admin_user:

        cursor.execute("INSERT INTO users (username, password, nickname, role) VALUES (%s, %s, %s, %s)",

                       ('admin', hash_password(admin_password), '系统管理员', 'admin'))

    elif not str(admin_user[0]).startswith(('scrypt:', 'pbkdf2:', 'argon2:')):

        cursor.execute("UPDATE users SET password=%s WHERE username='admin'", (hash_password(admin_password),))

    conn.commit()

    cursor.close()

    conn.close()

def auto_approve_stale():
    """Approve products that have remained pending for more than 24 hours."""
    conn = None
    cursor = None
    affected = 0
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(hours=24)
        cursor.execute(
            "UPDATE products SET status='approved' "
            "WHERE status='pending' AND created_at < %s",
            (cutoff,),
        )
        affected = cursor.rowcount
        conn.commit()
    except pymysql.MySQLError:
        if conn:
            conn.rollback()
        app.logger.exception('Failed to auto-approve stale products')
        return
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if affected:
        log_action('auto_approve', 'product', None, f'approved:{affected}')

def ensure_schema():
    """生产环境（gunicorn 走 wsgi.py）不会执行 __main__ 分支，
    必须在这里建表，否则新加的列永远不会创建，页面直接 500。"""
    try:
        init_db()
    except Exception as exc:
        # 建表失败不能让整个应用起不来，否则所有页面都是 500
        print(f"[schema] init_db failed: {exc}")

import routes.auth  # noqa: F401  # 登录/注册/登出/填学号
import routes.home  # noqa: F401  # 首页
import routes.products  # noqa: F401  # 商品发布/添加/标记已售/评价/详情 API
import routes.favorites  # noqa: F401  # 收藏
import routes.profile  # noqa: F401  # 个人中心
import routes.admin  # noqa: F401  # 管理后台


ensure_schema()

if __name__ == '__main__':

    app.run(host='0.0.0.0', debug=False, port=5000)
