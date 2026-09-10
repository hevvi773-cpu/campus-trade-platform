# Campus Second-Hand Trading Platform 🛒

> A semi-closed community C2C second-hand trading system for university students, built with Flask + MySQL, deployed and live on a public cloud server.

## 🌐 Live Demo

- **Live URL**: http://106.53.27.244 (domain name pending)
- Register an account directly to experience the full flow: register → publish → order → chat → review
- Responsive design for desktop / tablet / mobile (three breakpoints)

## 🎯 Background

Second-hand trading information on campus is scattered across QQ groups, campus channels, and confession walls, with three core pain points:

- **Hard to find**: Messages get buried quickly under new posts; finding a specific item takes forever
- **Opaque status**: No way to tell if an item is still available, already sold, or long forgotten
- **Inconsistent search**: Some channels support keyword search, others don't at all

This platform consolidates scattered information into a unified entry point, providing a complete trading loop: publish → review → search → order → chat → review → credit.

## ✨ Core Features

### Products & Trading

- Product publishing and review (auto-approve after 24h as fallback)
- Product search + tag filtering + three tabs (Selling / Wanted / Sold)
- Order trading (`SELECT ... FOR UPDATE` row-level lock prevents concurrent overselling)
- In-app messaging (entering from a product auto-carries product context, rendered as a centered product card in chat)
- Favorites (optimistic UI update + backend response correction)
- Review & credit system (S/A/B/C/D five tiers, auto-recalculated by scoring formula)

### Users & Permissions

- Three-tier permission system: Guest / Muted Student / Normal Student / Admin, with all permission checks centralized in `services/authz.py`
- Login rate limiting (5 consecutive failures on same username + IP → 10-minute lock)
- Site-wide CSRF protection (form `_csrf_token` / JSON API `X-CSRF-Token` header)
- Passwords hashed with werkzeug, Session Cookies set with `HTTPOnly + SameSite=Lax`

### Admin Dashboard

- Product review (single / batch approve, reject, delete)
- User management (mute / unmute / delete, fixed 7-day mute duration)
- Feedback management (reply to user feedback, triggers unread badge on user side)
- Data dashboard (7-day publish / transaction / registration trends, top 5 sellers by revenue, activity breakdown)

### Personal Center

- Trading statistics (items sold / bought, total amounts)
- Data visualization (6-month monthly trading bar chart, rating distribution, campus-wide credit tier distribution)
- My published products management (status filter dropdown, delete)
- Review records (sent / received)

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | Flask 3.1 (Blueprint split: messages / orders / feedback) |
| Database | MySQL 8 (utf8mb4, PyMySQL driver) |
| Template Engine | Jinja2 + Bootstrap 5.3 (CDN) |
| Charts | Chart.js (CDN) |
| Deployment | gunicorn + systemd, cloud server |
| Security | werkzeug password hashing, site-wide CSRF, login rate limiting, three-tier permissions |
| Auth Plugin | cryptography (MySQL caching_sha2_password) |

## 📁 Project Structure

```
app/
├── app_v3.py              # Flask app entry, DB config, ensure_schema() auto-migration
├── wsgi.py                # gunicorn entry point
├── csrf.py                # CSRF initialization
├── requirements.txt       # Dependencies
├── .env                   # Environment variables (DB / secret key / admin password)
├── routes/                # 9 route modules
│   ├── auth.py            # Login / register / logout / fill student ID
│   ├── home.py            # Homepage (search / tags / AJAX pagination)
│   ├── products.py        # Publish / detail API / mark sold / review
│   ├── favorites.py       # Favorites
│   ├── profile.py         # Personal center
│   ├── admin.py           # Admin dashboard
│   ├── messages.py        # Messaging (Blueprint)
│   ├── orders.py          # Orders (Blueprint)
│   └── feedback.py        # Feedback (Blueprint)
├── services/              # 11 business service modules
│   ├── authz.py           # Permission checks & decorators (single source of truth)
│   ├── auth_service.py    # Authentication & login rate limiting
│   ├── product_service.py # Shared product query logic
│   ├── order_service.py   # Order state machine & concurrency control
│   ├── message_service.py # Messaging & conversation aggregation
│   ├── notify_service.py  # Unified unread badge calculation
│   ├── profile_service.py # Personal center data assembly
│   ├── feedback_service.py
│   ├── audit_service.py   # Four types of audit logs
│   ├── constants.py       # Global constants
│   └── student_id.py
├── templates/             # Jinja2 templates (per-module directories, shared _badges.html)
└── static/                # Static assets (JS / user uploads)
```

## 🏗️ Engineering Highlights

### Code Evolution

- Refactored from a single-file `app_v3.py` (7,619 lines) into a modular architecture (9 routes + 11 services + per-module templates)
- 15 version iterations, each with a CHANGELOG record
- v14: structural refactoring; v15: removed abandoned confirm_code design residue (5 cleanup points, zero residue verified by full-repo grep)

### Quality & Security

- **P0 fix** (v3): Fixed `onclick` attribute quote conflict in admin dashboard that caused all review / mute / delete buttons to fail
- **500 hotfix** (v8): Fixed homepage 500 caused by `get_user_favorite_ids` missing `db_config` parameter
- **Privilege fix** (v12): Fixed confirm_code privilege escalation (previously any logged-in user could read the confirmation code from the detail API); v15 completely removed this dead feature
- **Concurrency safety**: Order placement uses row-level lock + affected-row count verification to prevent overselling and duplicate orders
- **Site-wide CSRF**: All POST requests enforce token validation
- **Login rate limiting**: 5 consecutive failures on same username + IP → 10-minute lock
- **SQL optimization**: Admin dashboard statistical queries reduced from 35 to 11 (4 stat cards + 4 daily metrics + 1 top-5 + 2 list queries)

### v15 Verification Results

- All 23 Python files passed `py_compile`
- 35 routes registered, 16 templates compiled
- Homepage / login page returned HTTP 200
- `/api/product` returned 18 fields, confirm_code removed, all other fields intact

## 📊 Real Data

| Metric | Value |
|---|---|
| Registered accounts | 26 (single-person multi-account end-to-end cross-validation) |
| Total products | 51 (pending 2 / approved 47 / rejected 2) |
| Code versions | 15 |
| Routes | 35 |
| Database tables | 11 |
| Admin dashboard SQL queries | 35 → 11 |
| Verified loop | Register→Publish→Review→Order→Confirm→Review→Credit recalculation |

> Not publicly launched due to privacy compliance considerations; above data comes from single-person multi-account cross-validation.

## 📐 Design Documents

All design documents are in the `docs/` directory and can be opened directly in a browser:

| Document | Description |
|---|---|
| [PRD V1.3](docs/校园二手交易平台_PRD_V1.3.md) | Complete product requirements document (106KB), including version evolution, 11-table DDL, API contracts, privacy compliance, 20 regression test items, and DEV-001~013 known issues |
| [Deployment Architecture](docs/01_部署架构图.html) | Overall deployment architecture and technology selection |
| [ER Diagram](docs/02_ER图.html) | Database entity-relationship design (11 tables) |
| [Core Business Flow](docs/03_核心业务流程图.html) | Full flow: publish → order → confirm → review |
| [State Machine](docs/04_状态机图.html) | Product review / trading / order / feedback state transitions |
| [Project Directory Structure](docs/05_项目目录结构图.html) | Code organization and module breakdown |
| [Role & Permission Matrix](docs/06_用户角色权限图.html) | Guest / Muted / Normal Student / Admin permission matrix |

## 🚀 Quick Start

### Requirements

- Python 3.9+
- MySQL 8.0+

### Local Development

```bash
# 1. Extract the code package
tar -xzf fix_patch_v15_no_confirm_code.tar.gz
cd app

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
# Edit .env and update the following:
#   SECONDHAND_DB_HOST / PORT / USER / PASSWORD / NAME
#   SECONDHAND_SECRET_KEY
#   SECONDHAND_ADMIN_PASSWORD

# 4. Start dev server
flask run
# or production mode
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

Visit http://localhost:5000

> On first launch, `ensure_schema()` automatically creates the database schema (executed at module import time, ensuring new columns are auto-added in production).

### Production Deployment

```bash
# Production: gunicorn + systemd
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

Live URL: http://106.53.27.244 (domain name pending)

## 🔐 Security Notes

- Passwords hashed with werkzeug `generate_password_hash`, verified with `check_password_hash`
- Session Cookies set with `HTTPOnly=True`, `SameSite=Lax`, `SECURE` configurable via environment variable
- All POST requests enforce CSRF validation; missing or invalid token returns 403
- Image uploads validated by extension + MIME double check, 5MB per-file limit, 15MB total request body limit
- All SQL parameterized; only static column names allowed in f-string concatenation
- Open redirect protection: `next` parameter only allows site-relative paths starting with a single `/`

> ⚠️ **Important**: The `.env` file in the code package contains development environment credentials (DB password, SECRET_KEY, admin password). Before public deployment, be sure to change all sensitive values and never commit a real `.env` to a public repository.

## 👤 Author

**Luhuihui (VER)**

- Southwest University · Big Data Management & Application
- Target role: AI Product Manager / Product Manager
- GitHub: [@hevvi773-cpu](https://github.com/hevvi773-cpu)

### Project Role

- **Coursework phase**: Responsible for backend + web frontend development (teammate handled mini-program frontend, other members handled experiment logs and reports)
- **Post-course phase**: Independently completed a dozen optimization iterations + public deployment + PRD documentation (as-built PRD, reverse-engineered from 13 historical versions)

## 📄 License

MIT License
