import pymysql


def record_action(db_config, username, action, target_type=None, target_id=None, detail=None):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO action_logs
                (username, action, target_type, target_id, detail)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (username, action, target_type, target_id, detail),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def record_login(db_config, username, ip, user_agent):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO login_logs (username, ip, user_agent)
            VALUES (%s, %s, %s)
            """,
            (username, ip, user_agent),
        )
        cursor.execute(
            """
            UPDATE users
            SET last_login = NOW(), login_count = login_count + 1
            WHERE username = %s
            """,
            (username,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def record_view(db_config, username, product_id, ip):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO view_logs (username, product_id, ip)
            VALUES (%s, %s, %s)
            """,
            (username, product_id, ip),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def record_search(db_config, username, keyword, result_count):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO search_logs (username, keyword, result_count)
            VALUES (%s, %s, %s)
            """,
            (username, keyword, result_count),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
