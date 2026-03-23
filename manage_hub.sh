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

show_menu() {
    echo -e "${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup (Python & Dependencies)"
    echo "2) Run Hub Manually"
    echo "3) Install/Restart as System Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx Reverse Proxy & SSL (HTTPS)"
    echo "6) Exit"
    echo -n "Choose an option: "
}

setup_app() {
    echo -e "${GREEN}[*] Updating system and installing Python...${NC}"
    sudo apt update && sudo apt install python3 python3-pip -y
    python3 "$PY_SCRIPT" setup
}

setup_https() {
    echo -e "${CYAN}--- Nginx & SSL Configuration ---${NC}"
    read -p "Enter your domain (e.g., hub.example.com): " DOMAIN
    if [ -z "$DOMAIN" ]; then echo "Domain cannot be empty."; return; fi

    echo -e "${GREEN}[*] Installing Nginx and Certbot...${NC}"
    sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y

    CONF_PATH="/etc/nginx/sites-available/$APP_NAME"
    echo -e "${GREEN}[*] Creating Nginx configuration...${NC}"
    
    sudo bash -c "cat > $CONF_PATH <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 50G;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"

    sudo ln -sf "$CONF_PATH" "/etc/nginx/sites-enabled/"
    sudo nginx -t && sudo systemctl restart nginx

    echo -n "Do you want to get an SSL certificate now? (y/n): "
    read -r INSTALL_SSL
    if [[ "$INSTALL_SSL" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        sudo certbot --nginx -d "$DOMAIN"
    fi
    echo -e "${GREEN}[✔] Nginx/HTTPS setup completed!${NC}"
}

install_service() {
    echo -e "${GREEN}[*] Creating Systemd service...${NC}"
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
}

while true; do
    show_menu
    read -r opt
    case $opt in
        1) setup_app ;;
        2) python3 "$PY_SCRIPT" run ;;
        3) install_service ;;
        4) sudo systemctl stop $APP_NAME && echo "Service stopped." ;;
        5) setup_https ;;
        6) exit 0 ;;
        *) echo -e "${RED}Invalid option.${NC}" ;;
    esac
done
