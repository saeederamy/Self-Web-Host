#!/bin/bash

# --- خود-تعمیری: حذف کاراکترهای ویندوزی از خودِ اسکریپت ---
sed -i 's/\r//' "$0"

APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR=$(pwd)

# تابع برای گرفتن ورودی مستقیم از ترمینال (ضد لوپ)
ask() {
    local p="$1"
    echo -n -e "$p"
    read -r res < /dev/tty
    echo "$res" | tr -d '\r\n '
}

while true; do
    echo -e "\n--- $APP_NAME Manager ---"
    echo "1) Setup  2) Run  3) Service  4) Stop  5) SSL  6) Exit"
    
    opt=$(ask "Choose: ")

    case "$opt" in
        1) sudo apt update && sudo apt install python3 python3-pip -y && python3 "$PY_SCRIPT" setup ;;
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
            echo "Done." ;;
        4) sudo systemctl stop $APP_NAME ;;
        5)
            DOMAIN=$(ask "Enter Domain: ")
            [ -z "$DOMAIN" ] && continue
            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            # تنظیم تمیز انجین‌اکس
            CONF="/etc/nginx/sites-available/$DOMAIN"
            sudo bash -c "cat > $CONF <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        client_max_body_size 10G;
    }
}
EOF"
            sudo rm -f /etc/nginx/sites-enabled/default
            sudo ln -sf "$CONF" /etc/nginx/sites-enabled/
            sudo nginx -t && sudo systemctl restart nginx
            sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
            ;;
        6) exit 0 ;;
        *) [ -n "$opt" ] && echo "Invalid: $opt" ;;
    esac
done
