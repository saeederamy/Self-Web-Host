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

# تابعی برای گرفتن ورودی تمیز (بدون کاراکتر ویندوز)
safe_read() {
    local prompt_msg="$1"
    echo -n -e "$prompt_msg"
    read -r user_input
    echo "$user_input" | tr -d '\r'
}

show_menu() {
    echo -e "${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup (Python & Defaults)"
    echo "2) Run Hub Manually (Debug mode)"
    echo "3) Install/Restart as System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & SSL (HTTPS)"
    echo "6) Exit"
}

setup_app() {
    echo -e "${GREEN}[*] Installing Python...${NC}"
    sudo apt update && sudo apt install python3 python3-pip -y
    python3 "$PY_SCRIPT" setup
}

setup_https() {
    echo -e "${CYAN}--- Nginx & SSL Setup ---${NC}"
    DOMAIN=$(safe_read "Enter your domain (e.g., hub.example.com): ")

    if [ -z "$DOMAIN" ]; then echo -e "${RED}Error: Domain cannot be empty.${NC}"; return; fi

    echo -e "${GREEN}[*] Installing Nginx & Certbot...${NC}"
    sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y

    # پیدا کردن پورت از فایل کانفیگ
    PORT=$(grep "PORT=" fileserver.conf | cut -d'=' -f2 | tr -d '\r')
    if [ -z "$PORT" ]; then PORT=5000; fi

    CONF_PATH="/etc/nginx/sites-available/$DOMAIN"
    echo -e "${GREEN}[*] Creating Nginx Config for port $PORT...${NC}"
    
    sudo bash -c "cat > $CONF_PATH <<EOF
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

    sudo ln -sf "$CONF_PATH" "/etc/nginx/sites-enabled/"
    sudo rm -f /etc/nginx/sites-enabled/default
    
    echo -e "${GREEN}[*] Testing Nginx and getting SSL...${NC}"
    sudo nginx -t && sudo systemctl restart nginx
    
    echo -e "${CYAN}Attempting to get SSL for $DOMAIN...${NC}"
    # دریافت خودکار سرتیفیکیت بدون پرسیدن سوال
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

    echo -e "${GREEN}[✔] HTTPS is now active at https://$DOMAIN${NC}"
}

install_service() {
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
    echo -e "${GREEN}[✔] Service is running in background.${NC}"
}

# --- Main Loop ---
while true; do
    show_menu
    opt=$(safe_read "Choose an option: ")
    
    case $opt in
        1) setup_app ;;
        2) python3 "$PY_SCRIPT" run ;;
        3) install_service ;;
        4) sudo systemctl stop $APP_NAME ; echo -e "${RED}Stopped.${NC}" ;;
        5) setup_https ;;
        6) exit 0 ;;
        "") continue ;; # اگر ورودی خالی بود دوباره منو را نشان بده
        *) echo -e "${RED}Invalid option: '$opt'${NC}" ; sleep 1 ;;
    esac
done
