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

# تابع برای نمایش منو
show_menu() {
    echo -e "${CYAN}===================================${NC}"
    echo -e "${CYAN}   $APP_NAME Management Tool${NC}"
    echo -e "${CYAN}===================================${NC}"
    echo "1) Initial Setup (Python & Defaults)"
    echo "2) Run Hub Manually (Debug mode)"
    echo "3) Install/Restart as System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & SSL (HTTPS)"
    echo "6) Exit"
    echo -e "${CYAN}-----------------------------------${NC}"
    echo -n "Choose an option: "
}

# --- Main Loop ---
while true; do
    show_menu
    # متد جدید برای جلوگیری از لوپ: خواندن مستقیم از ترمینال
    read -r opt < /dev/tty
    
    # حذف کاراکترهای مخفی احتمالی
    opt=$(echo "$opt" | tr -d '\r\n[:space:]')

    case "$opt" in
        1)
            echo -e "${GREEN}[*] Installing Python...${NC}"
            sudo apt update && sudo apt install python3 python3-pip -y
            python3 "$PY_SCRIPT" setup
            ;;
        2)
            python3 "$PY_SCRIPT" run
            ;;
        3)
            echo -e "${GREEN}[*] Creating System Service...${NC}"
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
            echo -e "${GREEN}[✔] Service is running!${NC}"
            ;;
        4)
            sudo systemctl stop $APP_NAME
            echo -e "${RED}[!] Service Stopped.${NC}"
            ;;
        5)
            # بخش Nginx و SSL
            echo -n "Enter domain (e.g. site.com): "
            read -r DOMAIN < /dev/tty
            DOMAIN=$(echo "$DOMAIN" | tr -d '\r\n[:space:]')
            
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
        client_max_body_size 10G;
    }
}
EOF"
            sudo ln -sf "$CONF" /etc/nginx/sites-enabled/
            sudo rm -f /etc/nginx/sites-enabled/default
            sudo nginx -t && sudo systemctl restart nginx
            sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            if [ -n "$opt" ]; then
                echo -e "${RED}Invalid option: '$opt'${NC}"
                sleep 1
            fi
            ;;
    esac
done
