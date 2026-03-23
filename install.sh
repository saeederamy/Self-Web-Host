#!/bin/bash
REPO_URL="https://raw.githubusercontent.com/saeederamy/Self-Web-Host/main"

echo "Cleaning old files..."
rm -f hub.py manage_hub.sh

echo "Downloading Black Hub..."
curl -sL "$REPO_URL/hub.py" | tr -d '\r' > hub.py
curl -sL "$REPO_URL/manage_hub.sh" | tr -d '\r' > manage_hub.sh

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
./manage_hub.sh
