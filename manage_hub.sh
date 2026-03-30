#!/bin/bash

# --- Config ---
APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR=$(pwd)
CONF_FILE="fileserver.conf"

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

ask() {
    echo -n -e "${CYAN}$1${NC}" >&2
    read -r res < /dev/tty
    echo "$res" | tr -d '\r\n '
}

# ایجاد میانبر سیستم (self-hub command)
if [ ! -f "/usr/local/bin/self-hub" ]; then
    sudo ln -sf "$WORKING_DIR/manage_hub.sh" /usr/local/bin/self-hub
    sudo chmod +x /usr/local/bin/self-hub
fi

while true; do
    echo -e "\n${CYAN}--- $APP_NAME Management Tool ---${NC}"
    echo "1) Initial Setup"
    echo "2) Run Hub Manually (Debug)"
    echo "3) Install/Restart Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & Auto SSL (Certbot)"
    echo "6) Setup Nginx & Manual SSL (Custom Certs)"
    echo -e "${YELLOW}7) Show Credentials & Info${NC}"
    echo -e "${RED}8) Full Uninstall (Nuclear Option)${NC}"
    echo "9) Exit"
    
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
        4) sudo systemctl stop $APP_NAME ; echo "Stopped." ;;
        5)
            DOMAIN=$(ask "Enter domain: ")
            [ -z "$DOMAIN" ] && continue
            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            PORT=$(grep "PORT=" $CONF_FILE | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000
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
                echo -e "DOMAIN=$DOMAIN" >> $CONF_FILE
                echo -e "${GREEN}[✔] Auto SSL & Nginx Ready.${NC}"
            fi ;;
        6)
            DOMAIN=$(ask "Enter domain: ")
            [ -z "$DOMAIN" ] && continue
            
            CERT_PATH=$(ask "Enter full path to SSL Certificate (e.g., /root/cert.crt): ")
            KEY_PATH=$(ask "Enter full path to SSL Private Key (e.g., /root/private.key): ")

            if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
                echo -e "${RED}[!] Certificate or Key file not found! Please check the paths and try again.${NC}"
                continue
            fi

            sudo apt update && sudo apt install nginx -y
            PORT=$(grep "PORT=" $CONF_FILE | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000

            sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    # Redirect HTTP to HTTPS
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate $CERT_PATH;
    ssl_certificate_key $KEY_PATH;

    # Basic SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

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
                echo -e "DOMAIN=$DOMAIN" >> $CONF_FILE
                echo -e "${GREEN}[✔] Custom Manual SSL & Nginx Ready.${NC}"
            else
                echo -e "${RED}[!] Nginx configuration test failed. Please check your certificate files.${NC}"
            fi ;;
        7)
            echo -e "\n${YELLOW}--- Current Configurations ---${NC}"
            if [ -f "$CONF_FILE" ]; then
                cat "$CONF_FILE"
            else
                echo "No configuration found. Run Setup first."
            fi ;;
        8)
            confirm=$(ask "ARE YOU SURE? This will delete EVERYTHING (y/n): ")
            if [ "$confirm" == "y" ]; then
                echo "Stopping and removing service..."
                sudo systemctl stop $APP_NAME 2>/dev/null
                sudo systemctl disable $APP_NAME 2>/dev/null
                sudo rm -f $SERVICE_FILE
                sudo systemctl daemon-reload
                
                echo "Removing Nginx configs..."
                D_NAME=$(grep "DOMAIN=" $CONF_FILE | cut -d'=' -f2)
                if [ -n "$D_NAME" ]; then
                    sudo rm -f /etc/nginx/sites-enabled/$D_NAME
                    sudo rm -f /etc/nginx/sites-available/$D_NAME
                    sudo systemctl restart nginx
                fi

                echo "Deleting files..."
                rm -f hub.py manage_hub.sh install.sh $CONF_FILE
                sudo rm -f /usr/local/bin/self-hub
                echo -e "${RED}Uninstall complete. Bye!${NC}"
                exit 0
            fi ;;
        9) exit 0 ;;
        *) [ -n "$opt" ] && echo "Invalid: $opt" ;;
    esac
done
