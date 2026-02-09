================================================================================
HestiaCP + Django + Gunicorn Setup - Complete Checklist
Prepared by: MohammadAmin Baranzehi
Website / Contact: hacktube.ir
Last updated: February 09, 2026
================================================================================

Prerequisites (Must be done before starting)
────────────────────────────────────────────
□ Domain already created in HestiaCP (e.g. example.com)
□ Django project copied to: /home/amin/web/example.com/public_html/
□ Virtualenv created and packages installed:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt   # gunicorn must be included
□ Run collectstatic and migrate:
   python manage.py collectstatic --noinput
   python manage.py migrate
□ In settings.py:
   - DEBUG = False (or True for initial debugging)
   - ALLOWED_HOSTS includes domain (e.g. ['pexample.com', '*'])
   - STATIC_URL = '/static/'
   - STATIC_ROOT = BASE_DIR / 'staticfiles'

Stage 1 – Place Custom NGINX Templates
────────────────────────────────────────────
□ Copy template files directly (no subfolder!) to:
   /usr/local/hestia/data/templates/web/nginx/django.tpl
   /usr/local/hestia/data/templates/web/nginx/django.stpl

□ Set correct permissions:
   sudo chown root:root /usr/local/hestia/data/templates/web/nginx/django.*
   sudo chmod 644 /usr/local/hestia/data/templates/web/nginx/django.*

Stage 2 – Apply Template in HestiaCP Panel
────────────────────────────────────────────
□ Log in to HestiaCP panel
□ Go to: Web → Edit domain (example.com)
□ In NGINX Template or Proxy Template section → select django
□ Click Save
□ (Strongly recommended) Force rebuild domain:
   sudo v-rebuild-web-domain amin example.com yes
   sudo systemctl restart nginx

Stage 3 – Create and Start Gunicorn Service
────────────────────────────────────────────
□ Run the helper script:
   add-gunicorn-service example.com user yourprojectname
   (or sudo /path/to/add-gunicorn-service.sh ... if not in PATH)

□ Restart service to apply:
   sudo systemctl restart gunicorn-example.com

Stage 4 – Verify Service, Socket and Permissions
────────────────────────────────────────────
□ Check service status (must be active (running)):
   sudo systemctl status gunicorn.example.com

□ Check socket existence and permissions:
   ls -l /home/amin/web/example.com/public_html/gunicorn.sock
   # Expected output: srw-rw---- 1 amin www-data ...

□ Fix socket permissions if wrong:
   sudo chown user:www-data gunicorn.sock
   sudo chmod 660 gunicorn.sock
   sudo systemctl restart gunicorn.example.com

□ Fix db.sqlite3 permissions (prevents readonly database error):
   ls -l db.sqlite3
   # Should be: -rw-rw-r-- 1 user www-data ...
   sudo chown user:www-data db.sqlite3
   sudo chmod 664 db.sqlite3

Stage 5 – Final Testing & Monitoring
────────────────────────────────────────────
□ Open site in browser: https://example.com
□ Try login and basic functionality

□ Monitor Gunicorn logs in real-time:
   journalctl -u gunicorn.example.com -f

□ Monitor NGINX logs if issue occurs:
   tail -f /var/log/nginx/error.log
   tail -f /home/amin/web/example.com/logs/nginx.error.log   # if exists

□ Optional direct socket test:
   curl --unix-socket gunicorn.sock http://localhost/

Quick Fixes for Common Issues
────────────────────────────────────────────
□ 502 Bad Gateway
   → Check NGINX log: tail -f /var/log/nginx/error.log
   → Fix socket permissions (chmod 660 + chown)
   → Rebuild domain and restart NGINX

□ Readonly database (db.sqlite3)
   → chown user:www-data db.sqlite3 && chmod 664 db.sqlite3

□ Default Hestia page still showing
   → mv index.html index.html.bak
   → sudo systemctl restart nginx

□ Template not showing in panel
   → Force rebuild: sudo v-rebuild-web-domain user yourdomain.com yes
   → Logout/login panel or clear browser cache

Important Post-Setup Notes
────────────────────────────────────────────
□ Set DEBUG = False in production
□ Rename or remove index.html if default page appears
□ After code update: git pull → collectstatic → migrate → restart gunicorn
□ For new domains: repeat stages 2–5 only (templates are already there)

Enjoy your stable Django setup on HestiaCP!
Prepared by: MohammadAmin Baranzehi
Website / Contact: hacktube.ir
================================================================================
