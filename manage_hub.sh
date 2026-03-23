#!/bin/bash

# --- Config ---
APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR=$(pwd)

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ask() {
    echo -n -e "${CYAN}$1${NC}" >&2
    read -r res < /dev/tty
    echo "$res" | tr -d '\r\n '
}

while true; do
    echo -e "\n${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup"
    echo "2) Run Manually"
    echo "3) Install/Restart Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & SSL"
    echo "6) Exit"
    
    opt=$(ask "Choose an option: ")

    case "$opt" in
        1) sudo apt update && sudo apt install python3 python3-pip -y ; python3 "$PY_SCRIPT" setup ;;
        2) python3 "$PY_SCRIPT" run ;;
        3)
            sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Black Hub
After=network.target
[Service]
User=$USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/python3 $WORKING_DIR/$PY_SCRIPT run
Restart=always
[Install]
WantedBy=multi-user.target
EOF
            sudo systemctl daemon-reload && sudo systemctl enable $APP_NAME && sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Service Started.${NC}" ;;
        4) sudo systemctl stop $APP_NAME ;;
        5)
            DOMAIN=$(ask "Enter domain: ")
            [ -z "$DOMAIN" ] && continue
            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            PORT=$(grep "PORT=" fileserver.conf | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000

            # استفاده از متد ضد-ارور برای نوشتن فایل کانفیگ
            sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 10G;
    }
}
EOF
            sudo rm -f /etc/nginx/sites-enabled/default
            sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
            
            if sudo nginx -t; then
                sudo systemctl restart nginx
                sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
                echo -e "${GREEN}[✔] SSL OK.${NC}"
            else
                echo -e "${RED}[!] Nginx test failed.${NC}"
            fi ;;
        6) exit 0 ;;
        *) [ -n "$opt" ] && echo "Invalid: $opt" ;;
    esac
done
