#!/bin/bash
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "Installing Black Hub..."
# دانلود و پاک‌سازی همزمان تمام فایل‌ها
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
# اجرای مستقیم منیجر
./manage_hub.sh
