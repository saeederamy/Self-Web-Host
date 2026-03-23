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

# تابع گرفتن ورودی امن از کیبورد
ask_user() {
    local prompt_msg="$1"
    echo -n -e "${CYAN}$prompt_msg${NC}" >&2
    read -r user_input < /dev/tty
    echo "$user_input" | tr -d '\r\n '
}

while true; do
    echo -e "\n${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup (Python & Dependencies)"
    echo "2) Run Hub Manually"
    echo "3) Install/Restart as System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx Reverse Proxy & SSL (HTTPS)"
    echo "6) Exit"
    
    opt=$(ask_user "Choose an option: ")

    case "$opt" in
        1)
            sudo apt update && sudo apt install python3 python3-pip -y
            python3 "$PY_SCRIPT" setup ;;
        2)
            python3 "$PY_SCRIPT" run ;;
        3)
            sudo bash -c "cat > $SERVICE_FILE <<EOF
[Unit]
Description=Black Hub File Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/python3 $WORKING_DIR/$PY_SCRIPT run
Restart=always

[Install]
WantedBy=multi-user.target
EOF"
            sudo systemctl daemon-reload
            sudo systemctl enable $APP_NAME
            sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Service Started Successfully.${NC}" ;;
        4)
            sudo systemctl stop $APP_NAME
            echo -e "${RED}[!] Service Stopped.${NC}" ;;
        5)
            DOMAIN=$(ask_user "Enter your domain (e.g. hub.example.com): ")
            [ -z "$DOMAIN" ] && continue

            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            
            # استخراج پورت
            PORT=$(grep "PORT=" fileserver.conf | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000

            CONF="/etc/nginx/sites-available/$DOMAIN"
            # استفاده از بک‌اسلش برای متغیرهای انجین‌اکس (حیاتی برای رفع ارور شما)
            sudo bash -c "cat > $CONF <<EOF
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
EOF"
            sudo rm -f /etc/nginx/sites-enabled/default
            sudo ln -sf "$CONF" /etc/nginx/sites-enabled/
            
            if sudo nginx -t; then
                sudo systemctl restart nginx
                sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
                echo -e "${GREEN}[✔] HTTPS is now LIVE!${NC}"
            else
                echo -e "${RED}[!] Nginx test failed. Fix config.${NC}"
            fi ;;
        6)
            exit 0 ;;
        *)
            if [ -n "$opt" ]; then echo -e "${RED}Invalid option: '$opt'${NC}" ; sleep 1 ; fi ;;
    esac
done
