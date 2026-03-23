#!/bin/bash
# Quick installer for Black Hub

REPO_URL="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main"

echo "Installing Black Hub..."
curl -sO "$REPO_URL/hub.py"
curl -sO "$REPO_URL/manage_hub.sh"

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
./manage_hub.sh