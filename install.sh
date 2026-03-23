#!/bin/bash
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "Installing Black Hub..."
# دانلود فایل‌ها و حذف کاراکترهای ویندوزی
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
# اجرای منیجر با محیط ایزوله برای جلوگیری از لوپ ورودی
exec ./manage_hub.sh
