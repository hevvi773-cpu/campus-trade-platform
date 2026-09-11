# -*- coding: utf-8 -*-
"""学号校验。

设计要点
--------
1. 默认关闭。开关 SECONDHAND_STUDENT_ID_REQUIRED 未开启时，本模块不做任何拦截，
   内测期完全不受影响（保留接口，随时可启用）。
2. 学号共 15 位，结构：
     第  1-2 位：学位   01 博士 / 11 硕士 / 22 本科
     第  3-6 位：入学年份（9 月以前不能使用本年）
     第  7-9 位：学院号（须在学院表内；研究所没有本科）
     第 10-12 位：专业号（经常新增撤销，不校验）
     第 13-15 位：个人号（不校验）
3. 对外只返回统一错误文案，不暴露错在第几位，也不提供学号示例。

启用前仍需 VER 确认的两项数据：
  - COLLEGE_CODES：学号里的学院号口径（现有招生目录口径为 337=商贸学院，
    与 VER 学号中的 603 不一致，待核对后填入）。
  - DEGREE_YEARS：硕士、博士的学制年限（本科 4 年已确认）。
"""

import os
from datetime import date

# ---------------------------------------------------------------- 学位

DEGREE_CODES = {
    '01': '博士',
    '11': '硕士',
    '22': '本科',
}

# 学制年限：本科 4 年已确认；硕/博待确认，先按常见值填，启用前请核对。
DEGREE_YEARS = {
    '22': 4,   # 本科
    '11': 3,   # 硕士（待确认）
    '01': 4,   # 博士（待确认）
}

UNDERGRAD_DEGREE_CODE = '22'

# ---------------------------------------------------------------- 学院

# 学院号 -> 学院名称。
# 当前为空：招生目录口径（337=商贸学院）与学号口径（603）不一致，待核对后填入。
COLLEGE_CODES = {}

# 研究所/研究院代码集合：这些单位没有本科生，
# 学号里出现 22（本科）+ 研究所号 应判为错误。启用前随学院表一起填。
RESEARCH_INSTITUTE_CODES = set()

# ---------------------------------------------------------------- 其它

STUDENT_ID_LENGTH = 15

# 对外统一错误文案：不说明错在哪、不给示例
ERROR_MESSAGE = '学号错误'

MIN_ENROLL_YEAR = 1950

def is_enabled():
    """学号校验总开关（默认关闭）。"""
    value = os.environ.get('SECONDHAND_STUDENT_ID_REQUIRED', '')
    return value.strip().lower() in ('1', 'true', 'yes', 'on')

def max_enroll_year(today=None):
    """入学年份上限：9 月以前不能使用本年。"""
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1

def parse(student_id):
    """拆出各段。返回 dict，格式不对时返回 None。"""
    if not student_id:
        return None
    sid = str(student_id).strip()
    if not sid.isdigit() or len(sid) != STUDENT_ID_LENGTH:
        return None
    return {
        'degree': sid[0:2],
        'enroll_year': sid[2:6],
        'college': sid[6:9],
        'major': sid[9:12],
        'personal': sid[12:15],
    }

def validity_window(student_id):
    """返回 (起始年月, 结束年月)，用于参考。格式不对返回 None。
    例：2023 级本科 -> (2023-09, 2027-06)
    """
    parts = parse(student_id)
    if not parts:
        return None
    year = int(parts['enroll_year'])
    years = DEGREE_YEARS.get(parts['degree'], 4)
    return (date(year, 9, 1), date(year + years, 6, 30))

def validate(student_id, today=None):
    """校验学号。返回 (是否通过, 原因)。

    原因仅用于服务端日志/排查，不要直接展示给用户——
    对外统一使用 ERROR_MESSAGE。
    """
    parts = parse(student_id)
    if parts is None:
        return False, 'format'

    if parts['degree'] not in DEGREE_CODES:
        return False, 'degree'

    try:
        year = int(parts['enroll_year'])
    except ValueError:
        return False, 'enroll_year'

    if year < MIN_ENROLL_YEAR or year > max_enroll_year(today):
        return False, 'enroll_year_range'

    # 学院号：表为空时跳过该步校验（内测期学院表尚未确定）
    if COLLEGE_CODES:
        if parts['college'] not in COLLEGE_CODES:
            return False, 'college'
        # 研究所没有本科
        if parts['degree'] == UNDERGRAD_DEGREE_CODE and parts['college'] in RESEARCH_INSTITUTE_CODES:
            return False, 'college_no_undergrad'

    # 专业号、个人号不做校验
    return True, 'ok'

def check(student_id, today=None):
    """对外接口：只返回统一文案。"""
    ok, _reason = validate(student_id, today)
    if ok:
        return True, ''
    return False, ERROR_MESSAGE
