#!/bin/bash
# آدرس مستقیم فایل‌ها
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "Cleaning old files..."
rm -f hub.py manage_hub.sh

echo "Downloading and fixing Black Hub..."
# دانلود و حذف فوری کاراکترهای ویندوز (\r)
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
# اجرای منیجر در یک محیط تمیز
/bin/bash ./manage_hub.sh
