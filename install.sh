#!/bin/bash
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "------------------------------------------"
echo "  Black Hub - Fresh Installation Started  "
echo "------------------------------------------"

# حذف فایل‌های قدیمی برای جلوگیری از تداخل
rm -f hub.py manage_hub.sh

# دانلود با حذف کاراکترهای مخفی (\r)
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub2.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

chmod +x manage_hub.sh

echo "Done! Starting the Manager..."
sleep 1
./manage_hub.sh
