#!/bin/bash

# --- Configuration ---
APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR=$(pwd)

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

while true; do
    echo -e "\n${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup (Python & Dependencies)"
    echo "2) Run Hub Manually"
    echo "3) Install/Restart as System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx Reverse Proxy & SSL (HTTPS)"
    echo "6) Exit"
    
    # چاپ پیام مستقیماً در خروجی خطا تا توسط متغیر ضبط نشود
    echo -n -e "${CYAN}Choose an option: ${NC}" >&2
    read -r opt < /dev/tty
    
    # پاکسازی ورودی
    opt=$(echo "$opt" | tr -d '\r\n ')

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
            sudo systemctl daemon-reload && sudo systemctl enable $APP_NAME && sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Service Started.${NC}" ;;
        4)
            sudo systemctl stop $APP_NAME
            echo -e "${RED}[!] Service Stopped.${NC}" ;;
        5)
            echo -n "Enter your domain: " >&2
            read -r DOMAIN < /dev/tty
            DOMAIN=$(echo "$DOMAIN" | tr -d '\r\n ')
            [ -z "$DOMAIN" ] && continue

            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            
            PORT=$(grep "PORT=" fileserver.conf | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000

            CONF="/etc/nginx/sites-available/$DOMAIN"
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
            sudo nginx -t && sudo systemctl restart nginx
            sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email ;;
        6)
            exit 0 ;;
        *)
            if [ -n "$opt" ]; then
                echo -e "${RED}Invalid option: '$opt'${NC}"
                sleep 1
            fi ;;
    esac
done
