#!/bin/bash
# Quick installer for Black Hub

REPO_URL="https://github.com/saeederamy/Self-Web-Host/main"

echo "Installing Black Hub..."
curl -sO "$REPO_URL/hub.py"
curl -sO "$REPO_URL/manage_hub.sh"

chmod +x manage_hub.sh

echo "Installation complete. Starting manager..."
./manage_hub.sh
