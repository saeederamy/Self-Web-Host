#!/bin/bash
REPO_URL="https://raw.githubusercontent.com/saeederamy/black-hub/main"
INSTALL_DIR="/opt/black-hub"

echo "------------------------------------------"
echo "  Black Hub - Global Installation         "
echo "------------------------------------------"

# ساخت پوشه اختصاصی پنل در سرور
sudo mkdir -p $INSTALL_DIR
cd $INSTALL_DIR || exit

echo "[*] Downloading Core Files from GitHub..."
# دانلود با حذف کاراکترهای مخفی (\r)
sudo curl -sL "$REPO_URL/hub.py" | tr -d '\r' | sudo tee hub.py > /dev/null
sudo curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' | sudo tee manage_hub.sh > /dev/null

sudo chmod +x manage_hub.sh

# ساخت کامند سراسری برای ترمینال
echo "[*] Creating global command 'black-hub'..."
sudo ln -sf "$INSTALL_DIR/manage_hub.sh" /usr/local/bin/black-hub
sudo chmod +x /usr/local/bin/black-hub

echo -e "\n[✔] Installation Successful!"
echo -e "================================================="
echo -e " You can now type 'black-hub' anywhere in "
echo -e " the terminal to open the management panel."
echo -e "=================================================\n"

sleep 2
# اجرای خودکار پنل پس از نصب
black-hub
