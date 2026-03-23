#!/bin/bash
# Quick installer for Black Hub

# آدرس اصلاح شده برای دسترسی مستقیم به فایل‌ها
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "Installing Black Hub..."
# دانلود اسکریپت اصلی و مدیریتی
curl -sLO "$REPO_URL/hub.py"
curl -sLO "$REPO_URL/manage_hub.sh"

# اجازه دسترسی اجرایی
chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
./manage_hub.sh
