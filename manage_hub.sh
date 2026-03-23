#!/bin/bash

APP_NAME="black-hub"
PY_SCRIPT="hub.py"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
WORKING_DIR=$(pwd)

while true; do
    echo -e "\n--- $APP_NAME Management Tool ---"
    echo "1) Initial Setup"
    echo "2) Run Manually"
    echo "3) Install as Service"
    echo "4) Stop Service"
    echo "5) Setup Nginx & SSL"
    echo "6) Exit"
    echo -n "Choose an option: "
    
    # خواندن ورودی مستقیماً از کنسول برای جلوگیری از تکرار منو
    read -r opt < /dev/tty
    opt=$(echo "$opt" | tr -d '\r\n ')

    case "$opt" in
        1)
            sudo apt update && sudo apt install python3 python3-pip -y
            python3 "$PY_SCRIPT" setup
            ;;
        2)
            python3 "$PY_SCRIPT" run
            ;;
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
            echo "Service Installed and Started."
            ;;
        4)
            sudo systemctl stop $APP_NAME
            echo "Service Stopped."
            ;;
        5)
            echo -n "Enter Domain: "
            read -r DOMAIN < /dev/tty
            DOMAIN=$(echo "$DOMAIN" | tr -d '\r\n ')
            sudo apt update && sudo apt install nginx certbot python3-certbot-nginx -y
            # تنظیمات Nginx و SSL (همان کدی که قبلاً دادم)
            ;;
        6)
            exit 0
            ;;
        *)
            if [ -z "$opt" ]; then continue; fi
            echo "Invalid option: '$opt'"
            sleep 1
            ;;
    esac
done
