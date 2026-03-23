#!/bin/bash
# Black Hub Quick Installer (Linux Optimized)

# آدرس دقیق و مستقیم فایل‌های خام
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "-----------------------------------"
echo "Installing Black Hub..."
echo "-----------------------------------"

# دانلود فایل‌ها با حذف کاراکترهای اضافه ویندوز در لحظه دانلود
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

# دادن دسترسی اجرایی
chmod +x manage_hub.sh

echo "Installation complete!"
echo "Starting Management Tool..."
sleep 2

# اجرای مدیریت
./manage_hub.sh
