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

# تابع برای گرفتن ورودی تمیز بدون لوپ
get_input() {
    local prompt_msg="$1"
    echo -n -e "${CYAN}$prompt_msg${NC}"
    read -r user_val < /dev/tty
    echo "$user_val" | tr -d '\r\n '
}

show_menu() {
    echo -e "\n${CYAN}===================================${NC}"
    echo -e "${CYAN}   $APP_NAME Management Tool${NC}"
    echo -e "${CYAN}===================================${NC}"
    echo "1) Initial Setup (Python & Config)"
    echo "2) Run Hub Manually"
    echo "3) Install/Restart System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & SSL (HTTPS)"
    echo "6) Exit"
    echo -e "${CYAN}-----------------------------------${NC}"
}

setup_https() {
    DOMAIN=$(get_input "Enter your domain (e.g. site.com): ")
    if [ -z "$DOMAIN" ]; then return; fi

    sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
    
    # پیدا کردن پورت
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
    # پاکسازی فایل‌های مزاحم و فعال‌سازی
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo ln -sf "$CONF" /etc/nginx/sites-enabled/
    
    sudo nginx -t && sudo systemctl restart nginx
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
    echo -e "${GREEN}[✔] HTTPS is ready at https://$DOMAIN${NC}"
}

# --- Main Loop ---
# حذف کاراکترهای ویندوزی از خودِ اسکریپت در لحظه اجرا (Self-Heal)
if [[ $(file "$0") == *"CRLF"* ]]; then
    tr -d '\r' < "$0" > "$0.tmp" && mv "$0.tmp" "$0" && chmod +x "$0"
fi

while true; do
    show_menu
    opt=$(get_input "Choose an option: ")

    case "$opt" in
        1) 
            sudo apt update && sudo apt install python3 python3-pip -y
            python3 "$PY_SCRIPT" setup ;;
        2) python3 "$PY_SCRIPT" run ;;
        3) 
            sudo bash -c "cat > $SERVICE_FILE <<EOF
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
EOF"
            sudo systemctl daemon-reload && sudo systemctl enable $APP_NAME && sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Service Started.${NC}" ;;
        4) sudo systemctl stop $APP_NAME ; echo "Stopped." ;;
        5) setup_https ;;
        6) exit 0 ;;
        *) [ -n "$opt" ] && echo -e "${RED}Invalid: '$opt'${NC}" ;;
    esac
done
