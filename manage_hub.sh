#!/bin/bash

# --- Config ---
APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR="/opt/black-hub"
CONF_FILE="fileserver.conf"
REPO_URL="https://raw.githubusercontent.com/saeederamy/black-hub/main"

# انتقال خودکار به پوشه نصب
mkdir -p "$WORKING_DIR"
cd "$WORKING_DIR" || exit 1

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

ask() {
    echo -n -e "${CYAN}$1${NC}" >&2
    read -e -r res < /dev/tty
    echo "$res" | tr -d '\r\n '
}

# ساخت میانبر در صورتی که کاربری بدون install.sh این فایل رو اجرا کرد
if [ ! -f "/usr/local/bin/black-hub" ]; then
    sudo ln -sf "$WORKING_DIR/manage_hub.sh" /usr/local/bin/black-hub
    sudo chmod +x /usr/local/bin/black-hub
fi

show_menu() {
    clear
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}       Black Hub Management Panel        ${NC}"
    echo -e "${GREEN}=========================================${NC}"
    
    if systemctl is-active --quiet $APP_NAME; then
        echo -e "Service Status: ${GREEN}▶ Running${NC}"
    else
        echo -e "Service Status: ${RED}🛑 Stopped${NC}"
    fi
    echo -e "-----------------------------------------"
    
    echo -e " ${YELLOW}1)${NC} 🚀 Initial Setup (Install & Config)"
    echo -e " ${YELLOW}2)${NC} 🔄 Update Panel (Fetch Latest Version)"
    echo -e " ${YELLOW}3)${NC} ▶️  Start Service"
    echo -e " ${YELLOW}4)${NC} 🛑 Stop Service"
    echo -e " ${YELLOW}5)${NC} ♻️  Restart Service"
    echo -e " ${YELLOW}6)${NC} 🛠️  Run Manually (Debug Mode)"
    echo -e " ${YELLOW}7)${NC} 🔐 Setup Nginx & Auto SSL (Certbot)"
    echo -e " ${YELLOW}8)${NC} 🔐 Setup Nginx & Manual SSL"
    echo -e " ${YELLOW}9)${NC} 🔑 Show Credentials & Info"
    echo -e "${RED}10)${NC} 🗑️  Full Uninstall (Nuclear Option)"
    echo -e "  ${RED}0)${NC} ❌ Exit"
    echo -e "-----------------------------------------"
}

while true; do
    show_menu
    opt=$(ask "Choose an option (0-10): ")

    case "$opt" in
        1) 
            sudo apt update && sudo apt install python3 python3-pip -y
            python3 "$PY_SCRIPT" setup
            
            sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Black Hub Web Server
After=network.target

[Service]
User=root
WorkingDirectory=$WORKING_DIR
ExecStart=/usr/bin/python3 $WORKING_DIR/$PY_SCRIPT run
Restart=always

[Install]
WantedBy=multi-user.target
EOF
            sudo systemctl daemon-reload
            sudo systemctl enable $APP_NAME
            sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Setup Complete and Service Started!${NC}"
            sleep 2
            ;;
        2)
            echo -e "${CYAN}Updating Black Hub to the latest version from GitHub...${NC}"
            sudo curl -sL "$REPO_URL/hub.py" | tr -d '\r' | sudo tee "$WORKING_DIR/hub.py" > /dev/null
            sudo curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' | sudo tee "$WORKING_DIR/manage_hub.sh" > /dev/null
            sudo chmod +x "$WORKING_DIR/manage_hub.sh"
            
            if systemctl is-active --quiet $APP_NAME; then
                sudo systemctl restart $APP_NAME
            fi
            echo -e "${GREEN}[✔] Update Complete!${NC}"
            sleep 2
            exec black-hub 
            ;;
        3) 
            sudo systemctl start $APP_NAME
            echo -e "${GREEN}[✔] Service Started.${NC}"
            sleep 1
            ;;
        4) 
            sudo systemctl stop $APP_NAME
            echo -e "${RED}[✔] Service Stopped.${NC}"
            sleep 1
            ;;
        5) 
            sudo systemctl restart $APP_NAME
            echo -e "${GREEN}[✔] Service Restarted.${NC}"
            sleep 1
            ;;
        6) 
            sudo systemctl stop $APP_NAME
            echo -e "${YELLOW}Running in debug mode. Press Ctrl+C to stop and return to menu.${NC}"
            python3 "$PY_SCRIPT" run 
            ;;
        7)
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
            fi
            sleep 2
            ;;
        8)
            DOMAIN=$(ask "Enter domain: ")
            [ -z "$DOMAIN" ] && continue
            
            CERT_PATH=$(ask "Enter full path to SSL Certificate (e.g., /root/cert.crt): ")
            KEY_PATH=$(ask "Enter full path to SSL Private Key (e.g., /root/private.key): ")

            if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
                echo -e "${RED}[!] Certificate or Key file not found!${NC}"
                sleep 2
                continue
            fi

            sudo apt update && sudo apt install nginx -y
            PORT=$(grep "PORT=" $CONF_FILE | cut -d'=' -f2 | tr -d '\r')
            [ -z "$PORT" ] && PORT=5000

            sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate $CERT_PATH;
    ssl_certificate_key $KEY_PATH;

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
                echo -e "${RED}[!] Nginx configuration test failed.${NC}"
            fi
            sleep 2
            ;;
        9)
            echo -e "\n${YELLOW}--- Current Configurations ---${NC}"
            if [ -f "$CONF_FILE" ]; then
                cat "$CONF_FILE"
            else
                echo "No configuration found. Run Setup first."
            fi
            ask "Press Enter to return to menu..."
            ;;
        10)
            confirm=$(ask "ARE YOU SURE? This will delete EVERYTHING (y/n): ")
            if [ "$confirm" == "y" ]; then
                echo "Stopping and removing service..."
                sudo systemctl stop $APP_NAME 2>/dev/null
                sudo systemctl disable $APP_NAME 2>/dev/null
                sudo rm -f $SERVICE_FILE
                sudo systemctl daemon-reload
                
                echo "Removing Nginx configs..."
                if [ -f "$CONF_FILE" ]; then
                    D_NAME=$(grep "DOMAIN=" $CONF_FILE | cut -d'=' -f2 | tr -d '\r')
                    if [ -n "$D_NAME" ]; then
                        sudo rm -f /etc/nginx/sites-enabled/$D_NAME
                        sudo rm -f /etc/nginx/sites-available/$D_NAME
                        sudo systemctl restart nginx
                    fi
                fi

                echo "Deleting files and commands..."
                # خروج از پوشه برای جلوگیری از خطای پاک کردن پوشه در حال استفاده
                cd /tmp || exit
                
                sudo rm -rf "$WORKING_DIR"
                sudo rm -f /usr/local/bin/black-hub
                sudo rm -f /usr/local/bin/self-hub
                
                echo -e "${RED}Uninstall complete. The 'black-hub' command has been removed. Bye!${NC}"
                exit 0
            fi 
            ;;
        0) clear; exit 0 ;;
        *) echo -e "${RED}Invalid option!${NC}"; sleep 1 ;;
    esac
done
