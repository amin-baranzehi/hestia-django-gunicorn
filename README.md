# HestiaCP + Django + Gunicorn — Deployment Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A **production-grade, modular deployment engine** for running Django applications on [HestiaCP](https://hestiacp.com/) using Gunicorn (unix socket) and NGINX reverse proxy.

> **Prepared by [MohammadAmin Baranzehi](https://amin.baranzehi.com)** — Cybersecurity & DevOps Engineer

---

## Features

- **Smart Auto-Detection** — Automatically identifies your Django project structure:
  - `config/wsgi.py` (modular / clean architecture)
  - `<project>/wsgi.py` (traditional `django-admin startproject`)
  - `wsgi.py` at root (flat layout)
- **One-Command Deployment** — Single command to deploy, configure, and start
- **Repair & Migration** — Fix previously deployed projects with `repair` command
- **Health Diagnostics** — Built-in `doctor` command with colour-coded reports
- **Security Hardened** — `--umask 007`, `ProtectSystem`, `PrivateTmp`, `NoNewPrivileges`
- **Dynamic Workers** — Auto-calculated: `(2 × CPU cores) + 1`
- **`.env` Support** — Auto-loads environment files via systemd `EnvironmentFile`
- **Static Files** — NGINX serves both `staticfiles/` and `static/` with priority matching
- **Backward Compatible** — Works with or without Python 3 on the server

---

## Architecture

```
hestia-django-gunicorn/
├── hdg                            # Global CLI executable (self-installing & updating)
├── cli.py                         # Python CLI engine (setup, repair, doctor, update)
├── add-gunicorn-service.sh        # Legacy wrapper (redirects to hdg)
├── core/                          # OOP Engine (SOLID principles)
│   ├── models.py                  # Data models & value objects (DRY)
│   ├── interfaces.py              # Abstract contracts (ISP & DIP)
│   ├── detector.py                # Project structure analyser (SRP)
│   ├── service_generator.py       # Systemd unit file generator (SRP)
│   ├── nginx_manager.py           # NGINX template manager (SRP)
│   ├── migrator.py                # Repair & upgrade engine (SRP)
│   ├── executor.py                # OS command executor (LSP)
│   └── doctor.py                  # Health check diagnostics (SRP)
├── templates/
│   ├── django-gunicorn.tpl        # NGINX HTTP template
│   └── django-gunicorn.stpl       # NGINX HTTPS template
└── tests/                         # Unit test suite
```

---

## Quick Start

### Prerequisites
- Ubuntu 22.04+ with HestiaCP (NGINX proxy mode)
- Domain created in HestiaCP panel
- Django project in `/home/<user>/web/<domain>/public_html/`
- Python 3.10+ with virtualenv and Gunicorn installed

### 1. One-Time Global Setup

Clone the repository anywhere (e.g. `/opt` or your home directory) and run `hdg` once:

```bash
git clone https://github.com/amin-baranzehi/hestia-django-gunicorn.git
cd hestia-django-gunicorn

# Installs templates to HestiaCP and links 'hdg' globally
sudo ./hdg install-templates
```

> **Note:** `hdg` automatically installs itself to `/usr/local/bin/hdg` (and `/usr/local/bin/v-django`). From now on, you can run `hdg` from **ANY** directory on your server!

### 2. Apply Template in HestiaCP Panel

1. Go to **Web → Edit Domain** (e.g. `example.com`)
2. Select **`django-gunicorn`** in NGINX / Proxy Template dropdown
3. Click **Save**

### 3. Deploy from ANY Directory

```bash
# Super fast — auto-detects WSGI, venv, and .env:
sudo hdg example.com amin

# Or with explicit setup keyword:
sudo hdg setup example.com amin
```

### 4. Verify & Diagnostics

```bash
sudo hdg doctor example.com amin
```

---

## Self-Updating

Whenever a new version is released, update your installation with a single command from anywhere:

```bash
sudo hdg update
```

This will:
1. Pull the latest code from git
2. Update NGINX templates in HestiaCP
3. Refresh global symlinks

---

## Repairing Previously Deployed Projects

If you deployed projects before and they have issues (502 errors, socket permissions, wrong WSGI module), `repair` fixes everything:

```bash
sudo hdg repair example.com amin
```

**What `repair` does:**
1. Reads the existing systemd service file and creates a timestamped backup
2. Re-detects your project structure (modular `config/` vs traditional vs flat)
3. Regenerates a hardened service file with `--umask 007`
4. Fixes `db.sqlite3` and static file permissions
5. Restarts Gunicorn and rebuilds NGINX configuration

---

## Commands Reference

| Command | Description |
| :--- | :--- |
| `hdg <domain> <user>` | Fast deploy (auto-detects project structure) |
| `hdg setup <domain> <user>` | Standard deploy |
| `hdg repair <domain> <user>` | Repair/upgrade an existing deployment |
| `hdg doctor <domain> <user>` | Run health diagnostics |
| `hdg update` | Self-update to latest version from git |
| `hdg install-templates` | Install NGINX templates to HestiaCP |
| `hdg status <domain>` | Show Gunicorn service status |
| `hdg install` | Re-link global commands in `/usr/local/bin` |

---

## Django Settings Required for Production (HTTPS)

Add these to your `settings.py` when deploying behind NGINX with SSL:

```python
# Trust the X-Forwarded-Proto header from NGINX (prevents CSRF 403 errors)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = ['https://yourdomain.com']
```

---

## Troubleshooting

| Issue | Solution |
| :--- | :--- |
| **502 Bad Gateway** | Run `sudo python3 cli.py repair domain user` |
| **CSRF 403 Forbidden** | Add `SECURE_PROXY_SSL_HEADER` to settings.py |
| **Readonly database** | `sudo chown user:www-data db.sqlite3 && sudo chmod 664 db.sqlite3` |
| **Default page showing** | `mv public_html/index.html public_html/index.html.bak` |
| **Static files 404** | Run `python manage.py collectstatic --noinput` |
| **Template not in panel** | Run `sudo v-rebuild-web-domain user domain yes` |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

**Prepared by [MohammadAmin Baranzehi](https://amin.baranzehi.com)**
