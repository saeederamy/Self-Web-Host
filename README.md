# 🛡️ Black Hub - Ultimate Self-Hosted File Manager & Streaming Platform

A powerful, highly secure, and visually stunning web-based file manager and streaming platform designed for seamless deployment on both Linux and Windows servers. **Black Hub** turns your server into a personal cloud storage with advanced sharing and media streaming features. No heavy dependencies required!

![Black Hub Preview](https://via.placeholder.com/1000x500.png?text=Shiny+Glass+UI+Preview) *(Note: Replace this link with an actual screenshot of your panel)*

---

## ✨ Key Features

### 📊 Smart Storage Dashboard
- **Admin Exclusive:** Visually displays the total server drive space, remaining free space, and the exact size occupied by files uploaded to the hub.

### 🎬 Streaming & Download Blocking (Stream Only)
- **Disable Download:** Admins can disable downloading for any specific media or file.
- Guests can only watch movies, listen to music, or view images online (Stream).
- Hides the download button, disables right-click, and blocks native browser player downloads.

### 🎨 Stunning Web UI (Shiny Glass)
- Completely redesigned UI featuring a modern **Glassmorphism** aesthetic.
- **5 Selectable Themes:** Dark, Light, Black & Blue, Black & Red, and an OLED-friendly **Pure Black** theme.
- Fully responsive design that works flawlessly on Desktop, Tablets, and Mobile devices.

### 🗂️ Advanced File Management
- **Drag & Drop Uploads** with real-time progress bars.
- Create folders, create files, rename, copy, **move with a tree-view menu**, and delete items easily.
- **Built-in Text Editor:** Edit code (Python, HTML, JS, configs) or text files directly inside the browser.
- **Bulk Download:** Compress and download entire folders as a `.zip` file with a single click.

### 🔗 Smart File Sharing
- **Public Links:** Generate instant sharing links for any file.
- **Limited Links:** Set a maximum download limit (e.g., expires after 3 downloads).
- **Secure Links:** Protect your shared files with a custom password.

### 🔒 Enterprise-Grade Security
- Dual access levels: **Admin** (full control) and **Guest** (view and stream/download only).
- **Item Locking:** Lock specific files or folders with unique passwords to prevent unauthorized access.
- **Anti Brute-Force System:** Automatically bans IP addresses for 24 hours after a set number of failed login attempts.
- **Live System Logs:** View access logs, IP activities, and system events directly from the Web UI.

---

## 🐧 Linux Installation (Ubuntu/Debian)

Deploy Black Hub on your Linux server in seconds using our automated installation script:
```bash
bash <(curl -sL https://raw.githubusercontent.com/saeederamy/black-hub/main/install.sh | tr -d '\r')
```

### 💻 Linux CLI Management
Once installed, Black Hub runs as a background service. You can manage it from anywhere in your terminal by typing:
```bash
bash <(curl -sL https://raw.githubusercontent.com/saeederamy/black-hub/main/install.sh | tr -d '\r')
```
for Edit Information:
```bash
nano /opt/black-hub/fileserver.conf
```
```bash
systemctl restart black-hub
```
For remove IP block:
```bash
rm /opt/black-hub/ip_blocks.json
systemctl restart black-hub
```
## 🐧 Linux Installation for Iran CDN  (Ubuntu/Debian)
Once installed, Black Hub runs as a background service. You can manage it from anywhere in your terminal by typing:
```bash
black-hub
```
For Iran CDN after install :
```bash
rm /opt/black-hub/hub.py
```
```bash
nano /opt/black-hub/hub.py
```
Copy hubir.py in after
```bash
systemctl restart black-hub
```



**CLI Features:** Run initial setup, update the panel directly from GitHub, start/stop the service, and **Auto SSL:** Install Nginx and secure your panel with Let's Encrypt (Certbot) in one click.

---

## 🪟 Windows Standalone Edition

The Windows version of Black Hub is compiled into a single, independent `.exe` file. **No Python or external dependencies required!**

### How to Install on Windows:
1. Download `blackhub_win.exe` from the **Releases** section.
2. Place the file in a dedicated folder on your Windows Server (e.g., `C:\BlackHub\`).
3. **Right-Click** the `.exe` and select **"Run as Administrator"**.
4. In the colorful CLI menu, choose **Option 1 (Initial Setup)** to configure your port, admin password, and install the native background service.
5. **Done!** Black Hub will register itself as a native Windows Service (`BlackHubService`) and will run silently in the background, even after system reboots.

*To change settings, stop the service, or fully uninstall it, simply run the `.exe` again as Administrator to access the management menu.*

---

## ⚠️ Security Disclaimer
The default password to enter the admin panel for both Linux and Windows setups is **`admin`**. Please ensure you change this password during the initial setup (via the CLI/CMD menu). For production Linux servers, it is highly recommended to use the CLI menu (Option 7 or 8) to put the panel behind a secure Nginx reverse proxy with SSL.

---

## 💖 Support the Project

If this tool has helped you manage your Windows services more efficiently, consider supporting its development. Your donations help keep the project updated and maintained.

### 💰 Crypto Donations

You can support me by sending **Litecoin** or **TON** to the following addresses:

| Asset | Wallet Address |
| :--- | :--- |
| **Litecoin (LTC)** | `ltc1qxhuvs6j0suvv50nqjsuujqlr3u4ekfmys2ydps` |
| **TON Network** | `UQAHI_ySJ1HTTCkNxuBB93shfdhdec4LSgsd3iCOAZd5yGmc` |

---

### 🌟 Other Ways to Help
* **Give a Star:** If you can't donate, simply giving this repository a ⭐ **Star** means a lot and helps others find this project.
* **Feedback:** Open an issue if you encounter bugs or have suggestions for improvements.

> **Note:** Please double-check the address before sending. Crypto transactions are irreversible. Thank you for your generosity!
