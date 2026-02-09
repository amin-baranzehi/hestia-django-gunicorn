# HestiaCP + Django + Gunicorn Deployment Guide

**Simple, fast and reliable way** to run Django applications on HestiaCP using Gunicorn (unix socket) and NGINX reverse proxy — without manual nginx.conf editing every time.

Prepared by: **MohammadAmin Baranzehi**  
Website/Contact: [hacktube.ir](https://hacktube.ir)  
Last updated: February 2026

## Features
- Unix socket for secure & fast communication
- Custom NGINX templates (no subfolder needed)
- One-command systemd service creation
- Static/media files served directly by NGINX
- Tested on Ubuntu 22.04 + HestiaCP 1.6.x+

## Requirements
- HestiaCP with NGINX proxy mode
- Django project in `/home/user/web/yourdomain.com/public_html/`
- Python 3.10+ and virtualenv
- Gunicorn installed in venv

## Step-by-Step Deployment Checklist

### 1. Place Custom NGINX Templates
Copy files **directly** (no subfolder) to:
/usr/local/hestia/data/templates/web/nginx/django-gunicorn.tpl
/usr/local/hestia/data/templates/web/nginx/django-gunicorn.stpl
textSet permissions:
```bash
sudo chown root:root /usr/local/hestia/data/templates/web/nginx/django-gunicorn.*
sudo chmod 644 /usr/local/hestia/data/templates/web/nginx/django-gunicorn.*
2. Apply Template in HestiaCP Panel

Go to: Web → Edit domain (e.g. example.com)
Select django-gunicorn in NGINX Template (or Proxy Template)
Click Save
Force rebuild (recommended):Bashsudo v-rebuild-web-domain amin example.com yes
sudo systemctl restart nginx

3. Create & Start Gunicorn Service
Run:
Bashadd-gunicorn-service example.com amin yourprojectname
# Example: add-gunicorn-service panel.example.com amin zamzam
Restart:
Bashsudo systemctl restart gunicorn-example.com
4. Verify Everything

Service status:Bashsudo systemctl status gunicorn-example.com
Socket check:Bashls -l /home/amin/web/example.com/public_html/gunicorn.sock
# Expected: srw-rw---- 1 amin www-data ...
Fix socket permissions if needed:Bashsudo chown amin:www-data gunicorn.sock
sudo chmod 660 gunicorn.sock
sudo systemctl restart gunicorn-example.com
Fix db.sqlite3 permissions:Bashsudo chown amin:www-data db.sqlite3
sudo chmod 664 db.sqlite3

5. Test & Monitor

Open: https://example.com
Real-time Gunicorn logs:Bashjournalctl -u gunicorn-example.com -f
NGINX logs:Bashtail -f /var/log/nginx/error.log

Quick Fixes

502 Bad Gateway → Check socket permissions + rebuild domain
Readonly database → chown/chmod db.sqlite3
Default page shows → mv index.html index.html.bak
Template not in list → Force rebuild + logout/login panel

Important Notes

Set DEBUG = False in production
After code changes: git pull → collectstatic → migrate → restart gunicorn
For new domains: Repeat steps 2–5 only (templates stay forever)

Enjoy your stable Django setup! 🚀
Prepared with ❤️ by MohammadAmin Baranzehi
https://hacktube.ir
