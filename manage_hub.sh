#!/bin/bash

# Check for root privileges
if [ "$EUID" -ne 0 ]; then 
  echo "Please run this script with sudo or as root."
  exit 1
fi

HUB_FILE="hub.py"
CURRENT_DIR=$(pwd)

while true; do
    clear
    echo "=========================================="
    echo "      HUB MANAGER - BLACK EDITION"
    echo "=========================================="
    echo "1) Setup & Create Service"
    echo "2) Remove Service"
    echo "3) Restart Service"
    echo "4) Show Status"
    echo "5) Exit"
    echo "=========================================="
    read -p "Select an option [1-5]: " OPT

    case $OPT in
        1)
            clear
            echo "--- Setup & Installation ---"
            read -p "Enter Project Folder Name: " FOLDER_NAME
            TARGET_DIR="/root/$FOLDER_NAME"

            if [ -f "$CURRENT_DIR/$HUB_FILE" ]; then
                mkdir -p "$TARGET_DIR"
                cp "$CURRENT_DIR/$HUB_FILE" "$TARGET_DIR/"
                echo "[✔] File $HUB_FILE copied to $TARGET_DIR"
            else
                echo "[✘] Error: $HUB_FILE not found in $CURRENT_DIR"
                read -p "Press Enter to continue..."
                continue
            fi

            cd "$TARGET_DIR"
            python3 hub.py setup

            SERVICE_FILE="/etc/systemd/system/$FOLDER_NAME.service"
            echo "[*] Creating systemd service..."
            cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=FileHub Service - $FOLDER_NAME
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$TARGET_DIR
ExecStart=/usr/bin/python3 $TARGET_DIR/hub.py run
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

            systemctl daemon-reload
            systemctl enable "$FOLDER_NAME.service"
            systemctl start "$FOLDER_NAME.service"

            echo "------------------------------------------"
            echo "[✔] Success! Project '$FOLDER_NAME' is active."
            echo "[*] Location: $TARGET_DIR"
            read -p "Press Enter to return to menu..."
            ;;

        2)
            clear
            echo "--- Remove Service ---"
            read -p "Enter the Project Folder Name to remove: " FOLDER_NAME
            SERVICE_NAME="$FOLDER_NAME.service"
            TARGET_DIR="/root/$FOLDER_NAME"

            systemctl stop "$SERVICE_NAME" 2>/dev/null
            systemctl disable "$SERVICE_NAME" 2>/dev/null
            rm "/etc/systemd/system/$SERVICE_NAME" 2>/dev/null
            
            echo "[?] Do you want to delete the storage folder $TARGET_DIR? (y/n)"
            read -p "> " DEL_FOLDER
            if [ "$DEL_FOLDER" = "y" ]; then
                rm -rf "$TARGET_DIR"
                echo "[✔] Folder deleted."
            fi

            systemctl daemon-reload
            systemctl reset-failed
            echo "[✔] Service removed."
            read -p "Press Enter to continue..."
            ;;

        3)
            clear
            read -p "Enter Project Folder Name to restart: " FNAME
            systemctl restart "$FNAME.service"
            echo "[✔] Service $FNAME restarted."
            read -p "Press Enter to continue..."
            ;;

        4)
            clear
            read -p "Enter Project Folder Name to check: " FNAME
            systemctl status "$FNAME.service"
            read -p "Press Enter to return to menu..."
            ;;

        5)
            clear
            exit 0
            ;;

        *)
            echo "Invalid option. Try again."
            sleep 1
            ;;
    esac
done