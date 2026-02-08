#!/usr/bin/env bash

# File: add-gunicorn-service.sh
# Usage: ./add-gunicorn-service.sh domain.com hestiauser projectname

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 domain hestia_user project_name"
    echo "Example: $0 example.com admin myproject"
    exit 1
fi

DOMAIN="$1"
USER="$2"
PROJECT="$3"

HOMEDIR="/home/$USER"
WEBDIR="$HOMEDIR/web/$DOMAIN/public_html"
VENV_BIN="$WEBDIR/venv/bin"
SOCK_PATH="$WEBDIR/gunicorn.sock"
SERVICE_NAME="gunicorn-$DOMAIN"

SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

if [ ! -d "$WEBDIR" ]; then
    echo "Error: Domain directory not found → $WEBDIR"
    exit 1
fi

if [ ! -d "$VENV_BIN" ]; then
    echo "Warning: Virtualenv not found → $VENV_BIN"
    echo "Assuming gunicorn is installed inside the venv anyway"
fi

echo "Creating service for: $DOMAIN"
echo "User: $USER"
echo "Project: $PROJECT"
echo "Socket path: $SOCK_PATH"
echo "Service name: $SERVICE_NAME"
echo ""

cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Gunicorn instance for $DOMAIN (Django)
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$WEBDIR
Environment="PATH=$VENV_BIN:/usr/local/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$VENV_BIN/gunicorn \\
          --access-logfile - \\
          --workers 3 \\
          --threads 2 \\
          --worker-class=gthread \\
          --bind unix:$SOCK_PATH \\
          --log-level=info \\
          $PROJECT.wsgi:application

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created: $SERVICE_FILE"

sudo systemctl daemon-reload
echo "→ daemon-reload completed"

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo ""
echo "Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -n 12

echo ""
echo "Socket check:"
ls -l "$SOCK_PATH" 2>/dev/null || echo "Socket not yet created (service must be running)"

echo ""
echo "If you get 502 Bad Gateway:"
echo "1. Make sure gunicorn is installed in venv: $VENV_BIN/pip install gunicorn"
echo "2. Run migrate & collectstatic if needed"
echo "3. Restart service: sudo systemctl restart $SERVICE_NAME"