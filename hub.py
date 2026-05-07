import http.server
import socketserver
import os
import urllib.parse
import hashlib
import sys
import argparse
import shutil
import re
import json
import uuid
import datetime
import tempfile
import time
import html
import threading

CONFIG_FILE = "fileserver.conf"
LINKS_FILE = "public_links.json"
LOCKS_FILE = "folder_locks.json"
LOG_FILE = "access_log.txt"
BLOCK_FILE = "ip_blocks.json"
NODL_FILE = "no_download.json"
USERS_FILE = "users.json"

# لیست سفید: این آی‌پی‌ها هرگز بن نمی‌شوند
WHITELIST_IPS = ['127.0.0.1', 'localhost', '::1']

_HUB_SIZE_CACHE = 0

def calculate_dir_size_bg(path):
    global _HUB_SIZE_CACHE
    while True:
        sz = 0
        try:
            for r, _, fs in os.walk(path):
                for n in fs:
                    fp = os.path.join(r, n)
                    if not os.path.islink(fp): 
                        sz += os.path.getsize(fp)
            _HUB_SIZE_CACHE = sz
        except: 
            pass
        time.sleep(15)

def load_json(p): 
    return json.load(open(p, 'r', encoding='utf-8')) if os.path.exists(p) else {}
    
def save_json(d, p): 
    json.dump(d, open(p, 'w', encoding='utf-8'))

def add_log(ip, act):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = open(LOG_FILE, "r", encoding="utf-8").readlines() if os.path.exists(LOG_FILE) else []
    lines.append(f"[{now}] IP: {ip} | Action: {act}\n")
    open(LOG_FILE, "w", encoding="utf-8").writelines(lines[-100:])

def check_ip(ip):
    if ip in WHITELIST_IPS: return False
    b = load_json(BLOCK_FILE)
    return ip in b and b[ip].get('block_until', 0) > time.time()

def rec_fail(ip, mx):
    if ip in WHITELIST_IPS: return
    b = load_json(BLOCK_FILE)
    now = time.time()
    if ip not in b: 
        b[ip] = {'fails': 1, 'last': now, 'block_until': 0}
    else:
        b[ip]['fails'] = 1 if now - b[ip]['last'] > 86400 else b[ip]['fails'] + 1
        b[ip]['last'] = now
        
    if b[ip]['fails'] >= mx: 
        b[ip]['block_until'] = now + 86400
        add_log(ip, "BANNED FOR 24H")
    save_json(b, BLOCK_FILE)

def clr_fail(ip):
    b = load_json(BLOCK_FILE)
    if ip in b: 
        del b[ip]
        save_json(b, BLOCK_FILE)

def load_config():
    if not os.path.exists(CONFIG_FILE): return None
    cfg = {}
    for line in open(CONFIG_FILE, "r", encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); cfg[k] = v
    return cfg

def load_users():
    return load_json(USERS_FILE)

def save_users(users):
    save_json(users, USERS_FILE)

def get_user_dir(base_upload_dir, username):
    d = os.path.join(os.path.abspath(base_upload_dir), "users", username)
    os.makedirs(d, exist_ok=True)
    return d

def get_user_used(base_upload_dir, username):
    d = os.path.join(os.path.abspath(base_upload_dir), "users", username)
    if not os.path.exists(d): return 0
    sz = 0
    for r, _, fs in os.walk(d):
        for n in fs:
            fp = os.path.join(r, n)
            if not os.path.islink(fp):
                try: sz += os.path.getsize(fp)
                except: pass
    return sz

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def is_locked(t_rel, l_path): return t_rel == l_path or t_rel.startswith(l_path + "/")

COMMON_STYLE = """
    :root {
        --bg-dark: #0a0a0a; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #1f1f1f 0%, #0a0a0a 70%);
        --glass-bg: rgba(255, 255, 255, 0.03);
        --glass-border: rgba(255, 255, 255, 0.1);
        --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        --accent: #ffffff;
        --accent-glow: rgba(255, 255, 255, 0.3);
        --accent-text: #000000;
        --neon-red: #ef4444;
        --neon-red-glow: rgba(239, 68, 68, 0.4);
        --neon-orange: #f97316;
        --neon-orange-glow: rgba(249, 115, 22, 0.4);
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --input-bg: rgba(0,0,0,0.4);
    }
    [data-theme="black-blue"] {
        --bg-dark: #0a0a0f; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #1a1a2e 0%, #0a0a0f 70%);
        --accent: #3b82f6;
        --accent-glow: rgba(59, 130, 246, 0.4);
        --accent-text: #ffffff;
    }
    [data-theme="black-red"] {
        --bg-dark: #0f0000; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #2a0808 0%, #0f0000 70%);
        --accent: #ef4444;
        --accent-glow: rgba(239, 68, 68, 0.4);
        --accent-text: #ffffff;
    }
    [data-theme="pure-black"] {
        --bg-dark: #000000; 
        --bg-gradient: none;
        --glass-bg: #000000;
        --glass-border: #333333;
        --glass-shadow: none;
        --accent: #ffffff;
        --accent-glow: rgba(255, 255, 255, 0.1);
        --accent-text: #000000;
        --text-main: #e5e5e5;
        --text-muted: #737373;
        --input-bg: #000000;
    }
    [data-theme="light"] {
        --bg-dark: #f8fafc; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #ffffff 0%, #e2e8f0 100%);
        --glass-bg: rgba(255, 255, 255, 0.6);
        --glass-border: rgba(0, 0, 0, 0.1);
        --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.05);
        --accent: #0f172a;
        --accent-glow: rgba(15, 23, 42, 0.2);
        --accent-text: #ffffff;
        --text-main: #0f172a;
        --text-muted: #475569;
        --input-bg: rgba(255,255,255,0.8);
    }
    body { 
        font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: var(--bg-dark); 
        background-image: var(--bg-gradient);
        color: var(--text-main); 
        margin: 0; 
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
        transition: background 0.3s ease, color 0.3s ease;
    }
    .glass-box { 
        background: var(--glass-bg); 
        backdrop-filter: blur(16px); 
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border); 
        border-radius: 16px; 
        box-shadow: var(--glass-shadow);
        transition: background 0.3s ease, border 0.3s ease, box-shadow 0.3s ease;
    }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); border-radius: 10px; }
    ::-webkit-scrollbar-thumb { background: var(--glass-border); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--accent); }
"""

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{site_name}</title>
<script>document.documentElement.setAttribute('data-theme', localStorage.getItem('hub_theme') || 'black-white');</script>
<style>
""" + COMMON_STYLE + """
.header { background: var(--glass-bg); backdrop-filter: blur(20px); border-bottom: 1px solid var(--glass-border); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 30px rgba(0,0,0,0.1); transition: all 0.3s ease; }
.logo { font-size: 22px; font-weight: 800; letter-spacing: 2px; color: var(--text-main); text-transform: uppercase; }
.header-controls { display: flex; align-items: center; gap: 15px; }
.badge { border: 1px solid var(--accent); padding: 4px 14px; border-radius: 50px; font-size: 11px; font-weight: 600; color: var(--accent); background: rgba(128, 128, 128, 0.1); box-shadow: 0 0 10px var(--accent-glow); text-transform: uppercase; white-space: nowrap; }
.theme-select { background: transparent; color: var(--text-main); border: 1px solid var(--glass-border); padding: 6px 10px; border-radius: 8px; font-size: 12px; font-family: inherit; outline: none; cursor: pointer; max-width: 140px; }
.theme-select option { background: var(--bg-dark); color: var(--text-main); }
.logout-link { color: var(--neon-red); text-decoration: none; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3); transition: 0.3s; white-space: nowrap; }
.logout-link:hover { background: var(--neon-red); color: #fff; box-shadow: 0 0 15px var(--neon-red-glow); }
.container { max-width: 1200px; margin: 0 auto; padding: 30px 25px; transition: all 0.3s ease; box-sizing: border-box; }
.search-box { width: 100%; background: var(--input-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 16px 20px; color: var(--text-main); font-size: 15px; margin-bottom: 25px; box-sizing: border-box; transition: 0.3s; font-family: inherit; }
.search-box:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }
.nav-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 15px; flex-wrap: wrap; }
.breadcrumbs { font-size: 14px; color: var(--text-muted); font-weight: 500; word-break: break-word; flex: 1; min-width: 200px; }
.breadcrumbs a { color: var(--text-main); text-decoration: none; transition: 0.2s; }
.breadcrumbs a:hover { color: var(--accent); text-shadow: 0 0 8px var(--accent-glow); }
.nav-buttons { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.file-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--glass-border); border-left: 2px solid transparent; transition: 0.2s; position: relative; gap: 10px; }
.file-item:first-child { border-top-left-radius: 16px; border-top-right-radius: 16px; }
.file-item:last-child { border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; border-bottom: none; }
.file-item:hover { background: var(--glass-border); border-left: 2px solid var(--accent); z-index: 50; }
.file-info { display: flex; align-items: center; gap: 15px; flex: 1; min-width: 0; }
.file-meta { display: flex; gap: 30px; font-size: 13px; color: var(--text-muted); justify-content: flex-end; padding-right: 15px; font-weight: 400; white-space: nowrap; }
.file-name { font-size: 15px; font-weight: 500; color: var(--text-main); text-decoration: none; word-break: break-word; overflow-wrap: anywhere; cursor: pointer; transition: 0.2s; display: inline-block; }
.file-name:hover { color: var(--accent); }
.actions { display: flex; align-items: center; gap: 12px; }
.btn { padding: 8px 16px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; border: 1px solid var(--glass-border); background: var(--glass-bg); color: var(--text-main); transition: all 0.3s ease; display: inline-flex; align-items: center; justify-content: center; font-family: inherit; backdrop-filter: blur(5px); white-space: nowrap; }
.btn:hover { background: var(--glass-border); transform: translateY(-2px); box-shadow: 0 5px 15px var(--glass-shadow); }
.btn-action { background: rgba(128, 128, 128, 0.1); color: var(--accent); border-color: var(--accent-glow); }
.btn-action:hover { background: var(--accent); color: var(--accent-text); box-shadow: 0 0 20px var(--accent-glow); }
.kebab-btn { background: transparent; border: 1px solid var(--glass-border); color: var(--text-main); cursor: pointer; font-size: 18px; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; transition: 0.3s; flex-shrink: 0; }
.kebab-btn:hover { background: var(--glass-border); }
.dropdown-content { display: none; position: absolute; right: 24px; top: 55px; background: var(--bg-dark); backdrop-filter: blur(20px); border: 1px solid var(--glass-border); min-width: 200px; border-radius: 12px; z-index: 100; box-shadow: var(--glass-shadow); overflow: hidden; padding: 8px; }
.dropdown-content button { width: 100%; padding: 12px 16px; text-align: left; background: transparent; border: none; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; display: block; border-radius: 8px; transition: 0.2s; font-family: inherit; margin-bottom: 2px; }
.dropdown-content button:hover { background: var(--glass-border); color: var(--text-main); padding-left: 20px; }
.dropdown-content button.action-red:hover { background: rgba(239, 68, 68, 0.15); color: var(--neon-red); border-left: 2px solid var(--neon-red); }
.dropdown-content button.action-orange:hover { background: rgba(249, 115, 22, 0.15); color: var(--neon-orange); border-left: 2px solid var(--neon-orange); }
.dropdown-content button.action-accent:hover { background: rgba(128, 128, 128, 0.15); color: var(--accent); border-left: 2px solid var(--accent); }
.show { display: block; animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
.modal { display: none; position: fixed; z-index: 2000; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(15px); justify-content: center; align-items: center; }
.modal-content { width: 90%; height: 85%; max-width: 1000px; position: relative; display: flex; justify-content: center; align-items: center; animation: scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes scaleIn { from { transform: scale(0.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }
.modal-close { position: absolute; top: -40px; right: 0; color: #fff; font-size: 35px; cursor: pointer; opacity: 0.6; transition: 0.3s; line-height: 1; }
.modal-close:hover { opacity: 1; color: var(--neon-red); text-shadow: 0 0 15px var(--neon-red-glow); }
.tree-item { padding: 12px 15px; cursor: pointer; border-radius: 8px; transition: 0.2s; color: var(--text-muted); font-size: 14px; margin-bottom: 4px; display:flex; align-items:center; border: 1px solid transparent; word-break: break-all; }
.tree-item:hover { background: var(--glass-border); color: var(--text-main); }
.tree-item.selected { background: rgba(128, 128, 128, 0.15); color: var(--accent); font-weight: 600; border: 1px solid var(--accent-glow); box-shadow: 0 0 15px var(--accent-glow); }
iframe, video, img { border-radius: 12px; border: 1px solid var(--glass-border); max-width: 100%; max-height: 100%; background: rgba(0,0,0,0.5); box-shadow: var(--glass-shadow); }
@media (max-width: 768px) {
    .header { flex-direction: column; padding: 15px; gap: 15px; }
    .header-controls { width: 100%; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
    .container { padding: 15px 12px; }
    .file-meta { display: none; }
    .file-item { padding: 12px 15px; flex-wrap: wrap; }
    .actions { width: auto; justify-content: flex-end; }
    .file-info { width: 100%; margin-bottom: 5px; }
    .dropdown-content { right: 15px; top: 50px; }
    .nav-row { flex-direction: column; align-items: stretch; }
    .nav-buttons { justify-content: flex-start; }
    .btn { padding: 8px 12px; font-size: 12px; }
    .search-box { padding: 12px 15px; margin-bottom: 15px; }
    .modal-content { width: 95%; height: 90%; }
}
</style>
</head>
<body>
    <div class="header">
        <div class="logo">{site_name}</div>
        <div class="header-controls">
            <select id="themeSelector" class="theme-select" onchange="changeTheme(this.value)">
                <option value="black-white">⚫⚪ Black & White</option>
                <option value="black-blue">⚫🔵 Black & Blue</option>
                <option value="black-red">⚫🔴 Black & Red</option>
                <option value="pure-black">⚫⚫ Pure Black</option>
                <option value="light">⚪⚫ Light Mode</option>
            </select>
            <div style="display:flex; align-items:center; gap:10px;">
                <span class="badge">{role}</span>
                <button onclick="openChangePwd()" style="background:transparent;border:1px solid var(--glass-border);color:var(--text-muted);padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:0.3s;" onmouseover="this.style.color='var(--text-main)'" onmouseout="this.style.color='var(--text-muted)'">🔑 Password</button>
                <a href="/logout" class="logout-link">Logout</a>
            </div>
        </div>
    </div>
    
    <div class="container">
        <input type="text" id="search" class="search-box glass-box" placeholder="🔍 Search files..." onkeyup="doSearch()">
        <div class="nav-row">
            <div class="breadcrumbs">{breadcrumbs}</div>
            <div class="nav-buttons">
                {admin_top_btn}
                {admin_log_btn}
            </div>
        </div>
        {disk_dashboard}
        {admin_upload_area}
        <div class="file-list glass-box" id="list">{file_rows}</div>
    </div>

    <div id="batch-bar" class="glass-box" style="display:none; position:fixed; bottom:25px; left:50%; transform:translateX(-50%); z-index:1001; padding:15px 25px; align-items:center; gap:15px; box-shadow:0 10px 40px rgba(0,0,0,0.9); border-color:var(--accent); animation: fadeIn 0.3s ease;">
        <span id="batch-count" style="font-weight:900; color:var(--accent); font-size:14px; min-width:80px; text-align:center;">0 selected</span>
        <button class="btn action-accent" onclick="batchCopy()">📄 Copy</button>
        <button class="btn action-accent" onclick="batchMove()">✂️ Move</button>
        <button class="btn action-red" style="background:rgba(239,68,68,0.2); color:var(--neon-red); border-color:var(--neon-red);" onclick="batchDelete()">🗑️ Delete</button>
    </div>

    <div id="previewModal" class="modal"><div class="modal-content"><span class="modal-close" onclick="closePreview()">&times;</span><div id="previewBody" style="width:100%; height:100%; display:flex; justify-content:center; align-items:center;"></div></div></div>
    
    <div id="treeModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column; padding:25px; width:90%; max-width:500px; height:75%; box-sizing:border-box;">
            <h3 id="tree-title" style="margin:0 0 20px 0; color:var(--text-main); font-weight:600; font-size:18px; border-bottom:1px solid var(--glass-border); padding-bottom:15px; width:100%;">Select Destination</h3>
            <div id="tree-list" style="flex:1; width:100%; overflow-y:auto; background:var(--input-bg); border:1px solid var(--glass-border); border-radius:12px; padding:15px; box-sizing:border-box;"></div>
            <div style="margin-top:20px; display:flex; gap:12px; width:100%; justify-content:flex-end;">
                <button class="btn" onclick="document.getElementById('treeModal').style.display='none'">Cancel</button>
                <button class="btn btn-action" onclick="confirmTreeAction()">Confirm Action</button>
            </div>
        </div>
    </div>

    <div id="logModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column; padding:25px; width:90%; max-width:800px; height:85%; box-sizing:border-box;">
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:20px; border-bottom:1px solid var(--glass-border); padding-bottom:15px; flex-wrap:wrap; gap:10px;">
                <h3 style="margin:0; color:var(--text-main); font-weight:600;">System Access Logs</h3>
                <div style="display:flex; gap:12px;">
                    <a href="/download_logs" class="btn">📥 Download TXT</a>
                    <button class="btn" style="background:rgba(239, 68, 68, 0.15); color:var(--neon-red); border-color:rgba(239, 68, 68, 0.3);" onclick="clearLogs()">🗑️ Clear Logs</button>
                </div>
            </div>
            <textarea readonly id="log-viewer" style="width:100%; height:100%; background:rgba(0,0,0,0.8); color:#10b981; border:1px solid var(--glass-border); padding:20px; font-family:monospace; font-size:13px; resize:none; border-radius:12px; outline:none; box-sizing:border-box;"></textarea>
            <div style="margin-top:20px; display:flex; justify-content:flex-end; width:100%;">
                <button class="btn" onclick="document.getElementById('logModal').style.display='none'">Close</button>
            </div>
        </div>
    </div>

    <div id="editModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column; padding:25px; width:90%; max-width:800px; height:85%; box-sizing:border-box;">
            <h3 id="edit-name" style="margin:0 0 20px 0; color:var(--text-main); font-weight:600; border-bottom:1px solid var(--glass-border); padding-bottom:15px; width:100%; word-break:break-all;"></h3>
            <textarea id="edit-box" style="width:100%; height:100%; background:rgba(0,0,0,0.8); color:#f8fafc; border:1px solid var(--neon-orange); padding:20px; font-family:monospace; font-size:14px; resize:none; border-radius:12px; outline:none; box-sizing:border-box; box-shadow:inset 0 0 20px rgba(0,0,0,0.8);"></textarea>
            <div style="margin-top:20px; display:flex; gap:12px; width:100%; justify-content:flex-end;">
                <button class="btn" onclick="document.getElementById('editModal').style.display='none'">Cancel</button>
                <button class="btn" style="background:rgba(249, 115, 22, 0.15); color:var(--neon-orange); border-color:rgba(249, 115, 22, 0.4);" onclick="saveEdit()">💾 Save Changes</button>
            </div>
        </div>
    </div>

    <script>
        const currentDir = "{current_dir}";
        
        const themeSelector = document.getElementById('themeSelector');
        if(themeSelector) themeSelector.value = localStorage.getItem('hub_theme') || 'black-white';
        
        function changeTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('hub_theme', theme);
        }
        
        let selectedFiles = [];
        
        function toggleSelection(e) {
            e.stopPropagation();
            updateBatchBar();
        }
        
        function toggleAll(e) {
            let cbs = document.querySelectorAll('.file-cb');
            cbs.forEach(cb => cb.checked = e.target.checked);
            updateBatchBar();
        }
        
        function updateBatchBar() {
            selectedFiles = Array.from(document.querySelectorAll('.file-cb:checked')).map(cb => cb.value);
            let bar = document.getElementById('batch-bar');
            if(selectedFiles.length > 0) {
                bar.style.display = 'flex';
                document.getElementById('batch-count').innerText = selectedFiles.length + " selected";
            } else {
                bar.style.display = 'none';
            }
        }
        
        function batchDelete() {
            if(confirm('Permanently delete ' + selectedFiles.length + ' items?')) {
                fetch('/action', {
                    method:'POST', 
                    body:new URLSearchParams({action:'batch_delete', targets:selectedFiles.join('|'), dir:currentDir})
                }).then(()=>location.reload());
            }
        }
        function batchMove() { openTreeModal('batch_move', selectedFiles.join('|')); }
        function batchCopy() { openTreeModal('batch_copy', selectedFiles.join('|')); }

        function handleItemClick(url, type, lockId) {
            if (lockId) {
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 This item is Locked. Please enter password:");
                if (p) { document.cookie = "lock_" + lockId + "=" + p + ";path=/"; } 
                else { return; }
            }
            if (type === 'download') { 
                window.location.href = url.includes('?dl=1') ? url : url + "?dl=1"; 
            } else { 
                openPreview(url, type); 
            }
        }

        function doSearch() {
            let q = document.getElementById('search').value.toLowerCase();
            document.querySelectorAll('.file-item').forEach(item => {
                let name = item.getAttribute('data-name').toLowerCase();
                item.style.display = (name.includes(q) || name === '..') ? 'flex' : 'none';
            });
        }
        
        function toggleMenu(event, id) { 
            event.stopPropagation();
            document.querySelectorAll('.dropdown-content').forEach(d => { if(d.id !== id) d.classList.remove('show'); }); 
            document.getElementById(id).classList.toggle('show'); 
        }
        
        window.onclick = (e) => { 
            if (!e.target.closest('.dropdown-content') && !e.target.matches('.kebab-btn')) {
                document.querySelectorAll('.dropdown-content').forEach(d => d.classList.remove('show')); 
            }
        }
        
        function openPreview(url, type) {
            const body = document.getElementById('previewBody'); body.innerHTML = ''; document.getElementById('previewModal').style.display = 'flex';
            if (type === 'image') body.innerHTML = `<img src="${url}" oncontextmenu="return false;" style="pointer-events:none; max-width:90vw; max-height:90vh;">`;
            else if (type === 'video') body.innerHTML = `<video controls controlsList="nodownload" autoplay style="max-width:90vw; max-height:90vh;" oncontextmenu="return false;"><source src="${url}"></video>`;
            else if (type === 'audio') body.innerHTML = `<audio controls controlsList="nodownload" autoplay style="width:300px;" oncontextmenu="return false;"><source src="${url}"></audio>`;
            else if (type === 'pdf') body.innerHTML = `<iframe src="${url}#toolbar=0" style="width:90vw; height:90vh; background:#fff;" oncontextmenu="return false;"></iframe>`;
            else window.location.href = url + "?dl=1";
        }
        function closePreview() { document.getElementById('previewModal').style.display = 'none'; document.getElementById('previewBody').innerHTML = ''; }
        
        function openLogs() {
            document.getElementById('logModal').style.display='flex';
            document.getElementById('log-viewer').value = 'Loading...';
            fetch('/action', {method:'POST', body:new URLSearchParams({action:'get_logs'})}).then(r=>r.text()).then(t=>document.getElementById('log-viewer').value=t);
        }
        
        let treeAction = ''; let treeTarget = ''; let treeSelected = null;
        
        function openTreeModal(act, tgt) {
            treeAction = act; treeTarget = tgt; treeSelected = null;
            let icon = act.includes('move') ? '✂️ Move ' : '📄 Copy ';
            let lbl = act.includes('batch_') ? selectedFiles.length + ' items' : tgt;
            document.getElementById('tree-title').innerText = icon + lbl + " to...";
            document.getElementById('treeModal').style.display = 'flex';
            document.getElementById('tree-list').innerHTML = '<div style="color:var(--accent);text-align:center;padding:30px;font-weight:600;">Scanning Directories...</div>';
            
            fetch('/action', {method:'POST', body:new URLSearchParams({action:'get_tree'})}).then(r=>r.json()).then(dirs => {
                let h = '';
                dirs.forEach(d => {
                    let pad = d === '/' ? 0 : (d.split('/').length - 1) * 20;
                    let name = d === '/' ? 'Root Directory ( / )' : d.split('/').pop();
                    let folIcon = d === '/' ? '🖧' : '📁';
                    h += `<div class="tree-item" style="padding-left:${pad + 15}px" onclick="selectTreeItem(this, '${d}')">${folIcon} &nbsp; ${name}</div>`;
                });
                document.getElementById('tree-list').innerHTML = h;
            });
        }
        
        function selectTreeItem(el, path) {
            document.querySelectorAll('.tree-item').forEach(i => i.classList.remove('selected'));
            el.classList.add('selected');
            treeSelected = path === '/' ? '' : path.substring(1);
        }
        
        function confirmTreeAction() {
            if(treeSelected === null) return alert('Please select a destination folder first.');
            let params = {action: treeAction, dir: currentDir, dest: treeSelected};
            if(treeAction.startsWith('batch_')) {
                params.targets = treeTarget;
            } else {
                params.target = treeTarget;
            }
            fetch('/action', {method:'POST', body:new URLSearchParams(params)}).then(()=>location.reload());
        }

        function clearLogs() { if(confirm('Clear all system logs?')) fetch('/action', {method:'POST', body: new URLSearchParams({action:'clear_logs'}) }).then(()=>location.reload()); }
        function createFolder() { let n = prompt("New Folder Name:"); if(n) fetch('/action', {method:'POST', body: new URLSearchParams({action:'mkdir', target:n, dir:currentDir}) }).then(()=>location.reload()); }
        function createFile() { let n = prompt("New File Name (e.g. script.py):"); if(n) fetch('/action', {method:'POST', body: new URLSearchParams({action:'mkfile', target:n, dir:currentDir}) }).then(()=>location.reload()); }
        function deleteItem(n) { if(confirm('Permanently delete?')) fetch('/action', {method:'POST', body: new URLSearchParams({action:'delete', target:n, dir:currentDir}) }).then(()=>location.reload()); }
        function renameItem(n) { let nn = prompt("Rename to:", n); if(nn && nn !== n) fetch('/action', {method:'POST', body: new URLSearchParams({action:'rename', target:n, new_name:nn, dir:currentDir}) }).then(()=>location.reload()); }
        function moveItem(n) { openTreeModal('move', n); }
        function copyItem(n) { openTreeModal('copy', n); }
        function lockItem(n) { let pwd = prompt("Set Lock Password (leave empty to remove lock):"); if(pwd !== null) fetch('/action', {method:'POST', body: new URLSearchParams({action:'lock_item', target:n, dir:currentDir, pwd:pwd}) }).then(()=>location.reload()); }
        function toggleDl(n) { fetch('/action', {method:'POST', body: new URLSearchParams({action:'toggle_dl', target:n, dir:currentDir}) }).then(()=>location.reload()); }

        function askPathAndFetch(action, target, extraParams = {}) {
            let cPath = prompt("Enter custom link path (leave empty for random):\\nOnly letters, numbers, dash, underscore allowed.", "");
            if(cPath === null) return;
            let params = {action: action, target: target, dir: currentDir, custom_path: cPath};
            Object.assign(params, extraParams);
            fetch('/action', {method:'POST', body: new URLSearchParams(params)})
            .then(r=>r.text()).then(l=>{
                if(l === "EXISTS") alert("⚠️ This custom path already exists! Please try another one.");
                else { prompt("Link created successfully:", window.location.origin+l); location.reload(); }
            });
        }

        function shareItem(n) { askPathAndFetch('share', n); }
        function limitedShareItem(n) { let limit = prompt("Max Downloads:", "1"); if(limit && parseInt(limit)>0) askPathAndFetch('share_limit', n, {limit:parseInt(limit)}); }
        function pwdShareItem(n) { let pwd = prompt("Set Link Password:"); if(pwd) askPathAndFetch('share_pwd', n, {pwd:pwd}); }
        function renewItem(n) { if(confirm('Generate a new link? (Old link will expire)')) askPathAndFetch('renew', n); }
        
        function unshareItem(n) { fetch('/action', {method:'POST', body: new URLSearchParams({action:'unshare', target:n, dir:currentDir}) }).then(()=>location.reload()); }
        function viewLink(tk) { prompt("Current Shared Link:", window.location.origin + "/p/" + tk); }

        function editItem(n, lockId) {
            if (lockId) {
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 Locked File. Enter password to edit:");
                if (p) document.cookie = "lock_" + lockId + "=" + p + ";path=/";
                else return;
            }
            fetch('/download/' + currentDir + '/' + n).then(r => r.text()).then(t => {
                document.getElementById('edit-name').innerText = "📝 Editing: " + n;
                document.getElementById('edit-box').value = t;
                document.getElementById('edit-box').setAttribute('data-target', n);
                document.getElementById('editModal').style.display = 'flex';
            });
        }
        function saveEdit() {
            let n = document.getElementById('edit-box').getAttribute('data-target');
            let t = document.getElementById('edit-box').value;
            fetch('/action', {method:'POST', body: new URLSearchParams({action:'save_text', target:n, dir:currentDir, content:t}) }).then(()=>{ document.getElementById('editModal').style.display='none'; location.reload(); });
        }

        // --- بخش آپلود استاندارد (بدون تکه‌تکه شدن) ---
        window.pendingFiles = [];
        
        window.handleFilesSelect = function(files) {
            if(!files || files.length === 0) return;
            window.pendingFiles = Array.from(files);
            
            document.getElementById('drop-text').style.display = 'none';
            document.getElementById('selected-files').style.display = 'block';
            document.getElementById('btn-start-upload').style.display = 'block';
            document.getElementById('btn-confirm-publish').style.display = 'none';
            document.getElementById('progress-wrapper').style.display = 'none';
            document.getElementById('progress-bar').style.width = '0%';
            
            document.getElementById('selected-files').innerHTML = window.pendingFiles.map(function(f) {
                let sizeMB = (f.size / 1048576).toFixed(2);
                return '📄 ' + f.name + ' <span style="color:var(--text-muted); font-size:11px;">(' + sizeMB + ' MB)</span>';
            }).join('<br>');
        };

        window.startHubUpload = function(e) {
            e.preventDefault(); 
            e.stopPropagation();
            if(window.pendingFiles.length === 0) return;
            
            let btn = document.getElementById('btn-start-upload');
            btn.style.pointerEvents = 'none';
            btn.innerText = '⏳ Uploading... Please wait';
            document.getElementById('selected-files').style.opacity = '0.5';
            
            let fd = new FormData(); 
            for(let i=0; i<window.pendingFiles.length; i++) {
                fd.append('file', window.pendingFiles[i]);
            }
            
            document.getElementById('progress-wrapper').style.display = 'block';
            let progBar = document.getElementById('progress-bar');
            
            let xhr = new XMLHttpRequest(); 
            xhr.open('POST', '/upload?dir=' + encodeURIComponent(currentDir), true);
            
            xhr.upload.addEventListener('progress', function(ev) { 
                if(ev.lengthComputable) {
                    let percent = Math.round((ev.loaded / ev.total) * 100);
                    progBar.style.width = percent + '%'; 
                    progBar.style.boxShadow = "0 0 15px var(--accent)";
                }
            });
            
            xhr.onload = function() {
                btn.style.display = 'none';
                document.getElementById('btn-confirm-publish').style.display = 'block';
            };
            
            xhr.onerror = function() {
                alert('Upload connection failed! Check your network.');
                btn.innerText = '❌ Failed (Retry)';
                btn.style.pointerEvents = 'auto';
            };
            
            xhr.send(fd);
        };
        function openChangePwd() {
            document.getElementById('changePwdModal').style.display = 'flex';
            document.getElementById('cpwd-current').value = '';
            document.getElementById('cpwd-new').value = '';
            document.getElementById('cpwd-confirm').value = '';
            document.getElementById('cpwd-msg').textContent = '';
            document.getElementById('cpwd-current').focus();
        }
        function closeChangePwd() {
            document.getElementById('changePwdModal').style.display = 'none';
        }
        function submitChangePwd() {
            let cur  = document.getElementById('cpwd-current').value;
            let nw   = document.getElementById('cpwd-new').value;
            let conf = document.getElementById('cpwd-confirm').value;
            let msg  = document.getElementById('cpwd-msg');
            if (!cur || !nw || !conf) { msg.style.color='var(--neon-red)'; msg.textContent='All fields are required.'; return; }
            if (nw !== conf)          { msg.style.color='var(--neon-red)'; msg.textContent='New passwords do not match.'; return; }
            if (nw.length < 4)        { msg.style.color='var(--neon-red)'; msg.textContent='Password must be at least 4 characters.'; return; }
            let btn = document.getElementById('cpwd-btn');
            btn.disabled = true; btn.textContent = '⏳ Saving...';
            fetch('/api/change_pwd', {method:'POST', body: new URLSearchParams({current_pwd:cur, new_pwd:nw})})
              .then(r => r.text()).then(t => {
                btn.disabled = false; btn.textContent = '✅ Save Password';
                if (t === 'OK') {
                    msg.style.color = '#10b981';
                    msg.textContent = '✔ Password changed successfully!';
                    setTimeout(closeChangePwd, 1500);
                } else if (t === 'WRONG') {
                    msg.style.color = 'var(--neon-red)';
                    msg.textContent = '✖ Current password is incorrect.';
                } else {
                    msg.style.color = 'var(--neon-red)';
                    msg.textContent = '✖ Error. Try again.';
                }
              }).catch(() => { btn.disabled=false; btn.textContent='✅ Save Password'; msg.style.color='var(--neon-red)'; msg.textContent='Connection error.'; });
        }
        function adminAddUser() {
            let uname = prompt("New username:");
            if (!uname) return;
            let pwd = prompt("Password for " + uname + ":");
            if (!pwd) return;
            let quota = prompt("Storage quota in MB (0 = unlimited):", "0") || "0";
            fetch('/api/users', {method:'POST', body: new URLSearchParams({action:'add', username:uname, password:pwd, quota_mb:quota})})
              .then(r => r.text()).then(t => {
                if(t === "EXISTS") { alert("User '" + uname + "' already exists!"); return; }
                location.reload();
              });
        }
        function adminEditUser(uname, currentQuotaBytes) {
            let quotaMB = Math.round(currentQuotaBytes / (1024*1024));
            let newQuota = prompt("New quota in MB for " + uname + " (0 = unlimited):", quotaMB);
            if (newQuota === null) return;
            let newPwd = prompt("New password (leave blank to keep current):", "");
            fetch('/api/users', {method:'POST', body: new URLSearchParams({action:'edit', username:uname, quota_mb:newQuota, password:newPwd || ''})})
              .then(() => location.reload());
        }
        function adminDeleteUser(uname) {
            if (!confirm("Delete user '" + uname + "'? This will NOT delete their files.")) return;
            fetch('/api/users', {method:'POST', body: new URLSearchParams({action:'delete', username:uname})})
              .then(() => location.reload());
        }
    </script>

    <div id="changePwdModal" style="display:none;position:fixed;z-index:3000;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);backdrop-filter:blur(15px);justify-content:center;align-items:center;">
        <div class="glass-box" style="width:90%;max-width:380px;padding:30px;position:relative;animation:scaleIn .3s cubic-bezier(.175,.885,.32,1.275);">
            <button onclick="closeChangePwd()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:var(--text-muted);font-size:22px;cursor:pointer;line-height:1;">×</button>
            <h3 style="margin:0 0 22px;color:var(--text-main);font-size:16px;font-weight:700;">🔑 Change Password</h3>
            <div style="margin-bottom:14px;">
                <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:6px;">Current Password</label>
                <input id="cpwd-current" type="password" style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--glass-border);border-radius:10px;color:var(--text-main);font-size:14px;box-sizing:border-box;font-family:inherit;outline:none;" onkeydown="if(event.key==='Enter')document.getElementById('cpwd-new').focus()">
            </div>
            <div style="margin-bottom:14px;">
                <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:6px;">New Password</label>
                <input id="cpwd-new" type="password" style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--glass-border);border-radius:10px;color:var(--text-main);font-size:14px;box-sizing:border-box;font-family:inherit;outline:none;" onkeydown="if(event.key==='Enter')document.getElementById('cpwd-confirm').focus()">
            </div>
            <div style="margin-bottom:20px;">
                <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:6px;">Confirm New Password</label>
                <input id="cpwd-confirm" type="password" style="width:100%;padding:12px;background:var(--input-bg);border:1px solid var(--glass-border);border-radius:10px;color:var(--text-main);font-size:14px;box-sizing:border-box;font-family:inherit;outline:none;" onkeydown="if(event.key==='Enter')submitChangePwd()">
            </div>
            <p id="cpwd-msg" style="margin:0 0 16px;font-size:13px;min-height:18px;text-align:center;"></p>
            <button id="cpwd-btn" onclick="submitChangePwd()" style="width:100%;padding:13px;background:var(--accent);color:var(--accent-text);border:none;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;transition:.3s;box-shadow:0 0 20px var(--accent-glow);">✅ Save Password</button>
        </div>
    </div>

</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Access</title>
    <style>
        body { 
            display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; margin: 0;
            background: linear-gradient(45deg, #000000, #171717, #262626, #000000);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        @keyframes gradientBG { 0% {background-position: 0% 50%;} 50% {background-position: 100% 50%;} 100% {background-position: 0% 50%;} }
        
        .login-card { 
            padding: 40px; width: 90%; max-width: 340px; text-align: center; 
            background: rgba(20, 20, 20, 0.6);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.9);
            border-radius: 20px;
            position: relative; overflow: hidden;
            box-sizing: border-box;
            z-index: 10;
        }
        
        .login-card::before {
            content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 60%);
            z-index: -1; animation: pulse 6s ease-in-out infinite alternate;
        }
        @keyframes pulse { 0% {transform: scale(0.8);} 100% {transform: scale(1.2);} }

        h2 { color: #fff; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 30px; text-shadow: 0 0 20px rgba(255,255,255,0.2); word-break: break-word; }
        
        input { 
            width: 100%; padding: 16px; margin: 0 0 25px 0; 
            background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.2); 
            color: white; border-radius: 12px; box-sizing: border-box; outline: none; 
            font-size: 15px; text-align: center; letter-spacing: 4px; transition: 0.3s;
            font-family: inherit;
        }
        input:focus { border-color: #fff; box-shadow: 0 0 20px rgba(255,255,255,0.2); background: rgba(0,0,0,0.8); }
        input::placeholder { letter-spacing: 2px; color: rgba(255,255,255,0.3); }
        
        button { 
            width: 100%; padding: 16px; 
            background: #ffffff; color: #000000; 
            border: none; border-radius: 12px; cursor: pointer; 
            font-weight: 800; font-size: 15px; text-transform: uppercase; letter-spacing: 1px;
            box-shadow: 0 0 20px rgba(255,255,255,0.2); transition: 0.3s;
            font-family: inherit;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(255, 255, 255, 0.4); background: #e5e5e5; }
        
        .dev-link {
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        .dev-link a {
            color: rgba(255, 255, 255, 0.5);
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: 0.3s;
        }
        .dev-link a:hover {
            color: #fff;
            text-shadow: 0 0 15px rgba(255, 255, 255, 0.6);
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>{site_name}</h2>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="USERNAME" required autofocus style="letter-spacing:2px; margin-bottom:15px;">
            <input type="password" name="password" placeholder="••••••••" required>
            <button type="submit">Login</button>
        </form>
        
        <div class="dev-link">
            <a href="https://github.com/saeederamy" target="_blank">
                <svg height="18" width="18" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
                Developed by Saeed Eramy
            </a>
        </div>
    </div>
</body>
</html>
"""

def get_icon(filename, is_dir):
    if is_dir: return "📁"
    ext = filename.split('.')[-1].lower()
    if ext in ['mp4', 'mkv', 'mov']: return "🎬"
    if ext in ['mp3', 'wav']: return "🎵"
    if ext in ['jpg', 'png', 'gif', 'webp', 'jpeg']: return "🖼️"
    if ext in ['pdf']: return "📕"
    if ext in ['zip', 'rar', '7z', 'tar', 'gz']: return "📦"
    if ext in ['py', 'cpp', 'html', 'js', 'css', 'sql', 'sh', 'json']: return "💻"
    return "📄"

def get_preview_type(filename):
    ext = filename.split('.')[-1].lower()
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']: return 'image'
    if ext in ['mp4', 'webm']: return 'video'
    if ext in ['mp3', 'wav']: return 'audio'
    if ext in ['pdf']: return 'pdf'
    return None

class FileHubHandler(http.server.BaseHTTPRequestHandler):
    CONFIG = {}
    
    def get_client_ip(self):
        if "X-Forwarded-For" in self.headers:
            return self.headers["X-Forwarded-For"].split(",")[0].strip()
        if "X-Real-IP" in self.headers:
            return self.headers["X-Real-IP"].strip()
        return self.client_address[0]
        
    def address_string(self):
        return self.client_address[0]

    def get_role(self):
        ck = self.headers.get("Cookie", "")
        # Super admin check (config-based)
        if f"auth={hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest()}" in ck:
            return "admin"
        # Multi-user: all registered users get admin role within their own space
        users = load_users()
        for uname, udata in users.items():
            token = hashlib.sha256(f"{uname}:{udata['password']}".encode()).hexdigest()
            if f"auth_user={token}" in ck:
                return "admin"
        return None

    def get_logged_username(self):
        ck = self.headers.get("Cookie", "")
        if f"auth={hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest()}" in ck:
            return "admin"
        users = load_users()
        for uname, udata in users.items():
            token = hashlib.sha256(f"{uname}:{udata['password']}".encode()).hexdigest()
            if f"auth_user={token}" in ck:
                return uname
        return None

    def is_super_admin(self):
        """True only for the main admin (config-based), not regular users."""
        ck = self.headers.get("Cookie", "")
        return f"auth={hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest()}" in ck

    def get_safe_path(self, req_dir):
        uname = self.get_logged_username()
        if self.is_super_admin():
            base = os.path.abspath(self.CONFIG['UPLOAD_DIR'])
        else:
            base = get_user_dir(self.CONFIG['UPLOAD_DIR'], uname)
        t = os.path.abspath(os.path.join(base, req_dir.strip('/')))
        return t if t.startswith(base) else base

    def get_base_dir(self):
        uname = self.get_logged_username()
        if self.is_super_admin():
            return os.path.abspath(self.CONFIG['UPLOAD_DIR'])
        else:
            return get_user_dir(self.CONFIG['UPLOAD_DIR'], uname)

    def get_rel(self, p):
        base = self.get_base_dir()
        r = os.path.relpath(p, base).replace('\\', '/')
        return "" if r == "." else r

    def do_GET(self):
        client_ip = self.get_client_ip()
        
        if check_ip(client_ip):
            self._send_resp(f'<style>{COMMON_STYLE}</style><body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;margin:0;padding:20px;box-sizing:border-box;"><div class="glass-box" style="padding:40px;text-align:center;border-color:var(--neon-red);box-shadow:0 0 30px var(--neon-red-glow);max-width:400px;width:100%;"><h1 style="color:var(--neon-red);margin:0;font-weight:800;letter-spacing:2px;word-break:break-word;">🚫 ACCESS DENIED</h1><p style="color:var(--text-muted);margin-top:15px;font-size:15px;">Your IP has been temporarily blocked for 24 hours.</p></div></body>')
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/download_logs" and self.get_role() == "admin":
            if os.path.exists(LOG_FILE): return self._send_file(LOG_FILE, dl=True, name="access_log.txt")
            else: self.send_error(404); return
            
        if parsed.path.startswith("/p/"):
            tk = parsed.path.split("/p/")[1]; lns = load_json(LINKS_FILE)
            if tk in lns:
                link_data = lns[tk]
                target_rel = link_data.get('target') if isinstance(link_data, dict) else link_data
                limit = link_data.get('limit', -1) if isinstance(link_data, dict) else -1
                pwd = link_data.get('pwd', '') if isinstance(link_data, dict) else ''
                
                if pwd:
                    req_pwd = urllib.parse.parse_qs(parsed.query).get('pwd', [''])[0]
                    if req_pwd != pwd:
                        self._send_resp(f'<style>{COMMON_STYLE}</style><body style="display:flex;justify-content:center;align-items:center;height:100vh;margin:0;"><script>let p=prompt("Secure Link - Password Required:");if(p)window.location.href="?pwd="+p;else document.body.innerHTML="<div class=\'glass-box\' style=\'padding:30px;color:var(--neon-red);\'>Access Denied</div>";</script></body>')
                        return
                        
                target = self.get_safe_path(target_rel)
                if os.path.isfile(target):
                    add_log(client_ip, f"Public Link Download: {target_rel}")
                    if limit > 0:
                        lns[tk]['limit'] -= 1
                        if lns[tk]['limit'] <= 0: del lns[tk]
                        save_json(lns, LINKS_FILE)
                    return self._send_file(target, dl=True)
            return self.send_error(404)
        
        role = self.get_role()
        if not role: 
            html_out = LOGIN_HTML.replace('{site_name}', str(self.CONFIG.get('SITE_NAME', 'BLACK HUB')))
            self._send_resp(html_out)
            return
        
        q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]; curr = self.get_safe_path(q)
        rel_curr = self.get_rel(curr)
        
        if parsed.path.startswith("/zip/"):
            target = self.get_safe_path(urllib.parse.unquote(parsed.path[5:]))
            if not self.check_item_lock(self.get_rel(target)): return
            if os.path.isdir(target):
                add_log(client_ip, f"Downloaded ZIP: {self.get_rel(target)}")
                tmp_base = tempfile.mktemp(); shutil.make_archive(tmp_base, 'zip', target); zip_path = tmp_base + '.zip'
                self._send_file(zip_path, dl=True, name=os.path.basename(target)+".zip"); os.remove(zip_path)
            else:
                self.send_error(404)
            return
            
        if parsed.path == "/": 
            if self.check_item_lock(rel_curr): self._serve_ui(role, curr, q)
            
        elif parsed.path.startswith("/download/"):
            target = self.get_safe_path(urllib.parse.unquote(parsed.path[10:]))
            rel = self.get_rel(target)
            if not self.check_item_lock(rel): return
            
            is_dl = urllib.parse.parse_qs(parsed.query).get('dl', ['0'])[0] == '1'
            ndl = load_json(NODL_FILE)
            if role != 'admin' and rel in ndl and is_dl:
                self._send_resp(f'<style>{COMMON_STYLE}</style><body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;margin:0;padding:20px;box-sizing:border-box;"><div class="glass-box" style="padding:40px;text-align:center;border-color:var(--neon-orange);max-width:400px;width:100%;"><h1 style="color:var(--neon-orange);margin:0;font-weight:800;letter-spacing:2px;">👀 STREAM ONLY</h1><p style="color:var(--text-muted);margin-top:15px;font-size:15px;">The administrator has disabled downloading for this file.</p><button onclick="window.close()" style="margin-top:20px; padding:10px 20px; background:var(--glass-border); border:none; color:white; border-radius:8px; cursor:pointer;">Close</button></div></body>')
                return

            if os.path.isfile(target): 
                add_log(client_ip, f"{'Downloaded' if is_dl else 'Streamed'} File: {rel}")
                self._send_file(target, dl=is_dl)
            else:
                self.send_error(404)
                
        elif parsed.path == "/logout":
            add_log(client_ip, "Logged Out")
            self.send_response(302)
            self.send_header("Set-Cookie", "auth=; Max-Age=0; Path=/; HttpOnly")
            self.send_header("Set-Cookie", "auth_user=; Max-Age=0; Path=/; HttpOnly")
            self.send_header("Location", "/")
            self.end_headers()

    def check_item_lock(self, target_rel):
        role = self.get_role()
        if role == 'admin': return True
        locks = load_json(LOCKS_FILE)
        for l_path, l_pwd in locks.items():
            if is_in_locked_path(target_rel, l_path):
                h = hashlib.md5(l_path.encode()).hexdigest()
                if f"lock_{h}={l_pwd}" not in urllib.parse.unquote(self.headers.get('Cookie', '')):
                    self._send_resp(f'<script>let p=prompt("🔒 Locked Area. Password:"); if(p){{ document.cookie="lock_{h}="+p+";path=/"; location.reload(); }} else history.back();</script>')
                    return False
        return True

    def _serve_ui(self, role, curr, req_dir):
        pts = [p for p in req_dir.split('/') if p]; bc = f'<a href="/">Root</a>'; acc = ""
        for p in pts: acc += f"/{p}"; bc += f' <span style="opacity:0.3">/</span> <a href="/?dir={urllib.parse.quote(acc)}">{p}</a>'
        
        select_all_btn = '<label class="btn" style="padding:8px 12px; gap:6px;"><input type="checkbox" onchange="toggleAll(event)" style="accent-color:var(--accent);"> Select All</label>'
        admin_btn = '<button class="btn btn-action" onclick="createFolder()">+ New Folder</button><button class="btn btn-action" onclick="createFile()" style="margin-left:12px;">+ New File</button>'
        admin_log_btn = '<button class="btn" style="background:rgba(16, 185, 129, 0.15); color:var(--neon-green); border-color:rgba(16, 185, 129, 0.4);" onclick="openLogs()">📜 System Logs</button>' if self.is_super_admin() else ''
        
        up_area = '<div class="glass-box" id="drop-zone" onclick="if(event.target.tagName !== \'BUTTON\') document.getElementById(\'file-input\').click();" ondragover="event.preventDefault(); this.style.borderColor=\'var(--accent)\';" ondragleave="event.preventDefault(); this.style.borderColor=\'var(--glass-border)\';" ondrop="event.preventDefault(); this.style.borderColor=\'var(--glass-border)\'; window.handleFilesSelect(event.dataTransfer.files);" style="padding:25px; text-align:center; margin-bottom:25px; cursor:pointer; border: 2px dashed var(--glass-border); transition: 0.3s;"><p id="drop-text" style="font-size:14px; font-weight:500; color:var(--text-muted); margin:0;">☁️ Drag & Drop files here or click to select</p><input type="file" id="file-input" style="display:none;" multiple onchange="window.handleFilesSelect(this.files)"><div id="selected-files" style="display:none; margin-top:15px; font-size:13px; color:var(--text-main); max-height:100px; overflow-y:auto; text-align:left; padding:10px; background:rgba(0,0,0,0.3); border-radius:8px;"></div><button id="btn-start-upload" class="btn btn-action" style="display:none; margin-top:15px; width:100%; padding:12px;" onclick="window.startHubUpload(event)">🚀 Start Upload</button><button id="btn-confirm-publish" class="btn" style="display:none; margin-top:15px; width:100%; padding:12px; background:#10b981; color:white; border-color:#10b981; box-shadow:0 0 20px rgba(16, 185, 129, 0.4);" onclick="location.reload()">✅ Confirm & Publish</button><div id="progress-wrapper" style="display:none; height:4px; background:rgba(0,0,0,0.5); margin-top:15px; border-radius:10px; overflow:hidden;"><div id="progress-bar" style="width:0; height:100%; background:var(--accent); transition:width 0.2s;"></div></div></div>'
        
        disk_html = ""
        if role == 'admin':
            try:
                tot, usd, fre = shutil.disk_usage(self.CONFIG['UPLOAD_DIR'])
                dir_size = _HUB_SIZE_CACHE
                uname_logged = self.get_logged_username()
                
                if self.is_super_admin():
                    # Super admin: show full user management dashboard
                    users = load_users()

                    # ── حساب کلی quota ──
                    total_quota_allocated = sum(u.get('quota', 0) for u in users.values())
                    total_quota_used      = sum(get_user_used(self.CONFIG['UPLOAD_DIR'], u) for u in users)
                    unallocated           = max(0, tot - total_quota_allocated)
                    alloc_pct             = min(100, int(total_quota_allocated * 100 / tot)) if tot > 0 else 0
                    used_pct              = min(100, int(total_quota_used      * 100 / tot)) if tot > 0 else 0

                    # ── نوار کلی دیسک ──
                    disk_bar = f'''
                        <div style="padding:15px 20px 10px;">
                            <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-muted);margin-bottom:6px;">
                                <span>💾 Disk Usage</span>
                                <span>{format_size(usd)} used &nbsp;·&nbsp; {format_size(fre)} free &nbsp;·&nbsp; {format_size(tot)} total</span>
                            </div>
                            <div style="height:8px;background:rgba(255,255,255,0.07);border-radius:6px;overflow:hidden;position:relative;">
                                <div style="position:absolute;left:0;top:0;height:100%;width:{used_pct}%;background:#f97316;border-radius:6px;transition:width .5s;" title="Actually used: {format_size(total_quota_used)}"></div>
                                <div style="position:absolute;left:0;top:0;height:100%;width:{alloc_pct}%;background:rgba(59,130,246,0.35);border-radius:6px;" title="Allocated quota: {format_size(total_quota_allocated)}"></div>
                            </div>
                            <div style="display:flex;gap:18px;margin-top:8px;font-size:11px;flex-wrap:wrap;">
                                <span style="color:#f97316;">■ Used: {format_size(total_quota_used)}</span>
                                <span style="color:#3b82f6;">■ Allocated: {format_size(total_quota_allocated)}</span>
                                <span style="color:var(--text-muted);">■ Free (unallocated): {format_size(unallocated)}</span>
                            </div>
                        </div>'''

                    # ── ردیف‌های کاربران ──
                    user_rows = ""
                    for uname, udata in users.items():
                        used  = get_user_used(self.CONFIG['UPLOAD_DIR'], uname)
                        limit = udata.get('quota', 0)
                        limit_str  = format_size(limit) if limit > 0 else "Unlimited"
                        pct        = min(100, int(used * 100 / limit)) if limit > 0 else 0
                        bar_color  = "#ef4444" if pct > 85 else "#f97316" if pct > 60 else "#10b981"
                        bar_html   = (f'<div style="height:5px;background:rgba(255,255,255,0.08);border-radius:4px;'
                                      f'margin-top:5px;overflow:hidden;">'
                                      f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:4px;transition:width .5s;"></div>'
                                      f'</div>') if limit > 0 else ''
                        pwd_display = udata.get('plain_pwd', '(set before update)')
                        user_rows += f'''<div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--glass-border);gap:12px;flex-wrap:wrap;">
                            <div style="display:flex;align-items:center;gap:10px;min-width:160px;">
                                <span style="font-size:22px;">👤</span>
                                <div>
                                    <div style="font-weight:700;color:var(--text-main);font-size:14px;">{html.escape(uname)}</div>
                                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">🔑 <span style="font-family:monospace;letter-spacing:1px;color:var(--accent);">{html.escape(pwd_display)}</span></div>
                                </div>
                            </div>
                            <div style="flex:1;min-width:170px;">
                                <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted);">
                                    <span>{format_size(used)} used</span>
                                    <span>quota: {limit_str}</span>
                                </div>
                                {bar_html}
                            </div>
                            <div style="display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0;">
                                <button class="btn btn-action" style="font-size:11px;padding:5px 12px;" onclick="adminEditUser('{html.escape(uname)}', {limit})">✏️ Edit</button>
                                <button class="btn" style="font-size:11px;padding:5px 12px;color:var(--neon-red);border-color:rgba(239,68,68,0.4);" onclick="adminDeleteUser('{html.escape(uname)}')">🗑️ Delete</button>
                            </div>
                        </div>'''

                    add_user_btn = '<button class="btn btn-action" style="margin:12px 16px;font-size:13px;" onclick="adminAddUser()">➕ Add New User</button>'

                    disk_html = f"""<div class="glass-box" style="margin-bottom:20px;">
                        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:0;border-bottom:1px solid var(--glass-border);">
                            <div style="text-align:center;padding:14px 10px;border-right:1px solid var(--glass-border);">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;">Total Disk</div>
                                <div style="font-size:16px;font-weight:800;color:var(--text-main);margin-top:4px;">{format_size(tot)}</div>
                            </div>
                            <div style="text-align:center;padding:14px 10px;border-right:1px solid var(--glass-border);">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;">Free Disk</div>
                                <div style="font-size:16px;font-weight:800;color:#10b981;margin-top:4px;">{format_size(fre)}</div>
                            </div>
                            <div style="text-align:center;padding:14px 10px;border-right:1px solid var(--glass-border);">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;">Allocated</div>
                                <div style="font-size:16px;font-weight:800;color:#3b82f6;margin-top:4px;">{format_size(total_quota_allocated)}</div>
                            </div>
                            <div style="text-align:center;padding:14px 10px;border-right:1px solid var(--glass-border);">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;">Actually Used</div>
                                <div style="font-size:16px;font-weight:800;color:#f97316;margin-top:4px;">{format_size(total_quota_used)}</div>
                            </div>
                            <div style="text-align:center;padding:14px 10px;">
                                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;">Users</div>
                                <div style="font-size:16px;font-weight:800;color:var(--accent);margin-top:4px;">{len(users)}</div>
                            </div>
                        </div>
                        {disk_bar}
                        <div style="padding:8px 0;border-top:1px solid var(--glass-border);margin-top:4px;">
                            <div style="padding:10px 16px;font-size:12px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">👥 User Management</div>
                            {user_rows if user_rows else '<div style="padding:12px 16px;color:var(--text-muted);font-size:13px;">No users yet.</div>'}
                            {add_user_btn}
                        </div>
                    </div>"""
                else:
                    # Regular user with admin role: show their own storage info
                    users = load_users()
                    if uname_logged in users:
                        used = get_user_used(self.CONFIG['UPLOAD_DIR'], uname_logged)
                        limit = users[uname_logged].get('quota', 0)
                        limit_str = format_size(limit) if limit > 0 else "Unlimited"
                        pct = min(100, int(used * 100 / limit)) if limit > 0 else 0
                        bar_color = "#ef4444" if pct > 85 else "#f97316" if pct > 60 else "#10b981"
                        bar_html = f'<div style="height:6px;background:rgba(255,255,255,0.1);border-radius:4px;margin-top:6px;overflow:hidden;"><div style="width:{pct}%;height:100%;background:{bar_color};border-radius:4px;transition:width 0.5s;"></div></div>' if limit > 0 else ''
                        disk_html = f'<div class="glass-box" style="display:flex;align-items:center;gap:20px;padding:15px 20px;margin-bottom:20px;flex-wrap:wrap;"><span style="font-size:24px;">💾</span><div style="flex:1;min-width:150px;"><span style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Your Storage</span><br><span style="font-weight:700;color:var(--text-main);">{format_size(used)}</span> <span style="color:var(--text-muted);font-size:13px;">/ {limit_str}</span>{bar_html}</div></div>'
                        disk_html += f'<div class="glass-box" style="display:flex; justify-content:space-around; align-items:center; padding:15px; margin-bottom:20px; flex-wrap:wrap; gap:10px;"><div style="text-align:center;"><span style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Total Drive Space</span><br><span style="font-size:15px; font-weight:800; color:var(--text-main);">{format_size(tot)}</span></div><div style="text-align:center;"><span style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">Free Space Remaining</span><br><span style="font-size:15px; font-weight:800; color:#10b981;">{format_size(fre)}</span></div></div>'
            except Exception as ex:
                disk_html = ""

        lns = load_json(LINKS_FILE)
        locks = load_json(LOCKS_FILE)
        ndl = load_json(NODL_FILE)
        
        link_map = {}
        for tk, data in lns.items():
            tgt = data.get('target') if isinstance(data, dict) else data
            if tgt not in link_map: link_map[tgt] = []
            link_map[tgt].append((tk, data))

        rows = ""
        if pts: rows += f'<div class="file-item" data-name=".."><div class="file-info"><span style="font-size:20px">🔙</span><a href="/?dir={urllib.parse.quote("/".join(pts[:-1]))}" class="file-name" style="color:var(--accent);">Return to Parent</a></div></div>'
        
        try:
            entries = list(os.scandir(curr))
            entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
        except: entries = []
        
        for e in entries:
            f = e.name
            if f in [CONFIG_FILE, LINKS_FILE, LOCKS_FILE, LOG_FILE, BLOCK_FILE, NODL_FILE, sys.argv[0].split('/')[-1].split('\\')[-1]]: continue
            
            is_d = e.is_dir()
            stat = e.stat()
            size = format_size(stat.st_size) if not is_d else "--"
            date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            full = e.path
            rel = self.get_rel(full)
            
            is_no_dl = rel in ndl
            lock_id = hashlib.md5(rel.encode()).hexdigest() if rel in locks else ""
            lock_info = f' <span style="color:var(--neon-orange); font-size:11px; margin-left:8px; text-shadow:0 0 8px var(--neon-orange-glow); white-space:nowrap;">[Pass: {locks[rel]}]</span>' if rel in locks and role == 'admin' else (' 🔒' if rel in locks else '')
            stream_badge = f'<span style="color:#3b82f6; font-size:10px; margin-left:8px; text-shadow:0 0 8px rgba(59,130,246,0.4); white-space:nowrap;">👀 Stream Only</span>' if is_no_dl else ""
            
            f_safe_js = f.replace('\\', '\\\\').replace("'", "\\'").replace('"', '&quot;')
            f_html = html.escape(f)
            
            cb_html = f'<input type="checkbox" class="file-cb" value="{f_html}" onclick="toggleSelection(event)" style="width:16px;height:16px;cursor:pointer;margin-right:10px;accent-color:var(--accent);">' if role == 'admin' else ''
            
            if is_d:
                nx = f"{req_dir}/{f}".strip('/')
                dl_zip_click = f"handleItemClick('/zip/{nx}', 'download', '{lock_id}')"
                admin_h = f'<button class="action-accent" onclick="{dl_zip_click}">📦 Download ZIP</button><button class="action-orange" onclick="lockItem(\'{f_safe_js}\')">🔒 Lock / Unlock</button><button class="action-orange" onclick="renameItem(\'{f_safe_js}\')">✏️ Rename</button><button class="action-accent" onclick="copyItem(\'{f_safe_js}\')">📄 Copy</button><button class="action-accent" onclick="moveItem(\'{f_safe_js}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f_safe_js}\')">🗑️ Delete</button>' if role == 'admin' else f'<button class="action-accent" onclick="{dl_zip_click}">📦 Download ZIP</button>'
                rows += f'<div class="file-item" data-name="{f_html}"><div class="file-info">{cb_html}<span style="font-size:18px; flex-shrink:0;">📁</span><a href="/?dir={urllib.parse.quote(nx)}" class="file-name">{f_html}{lock_info}</a></div><div class="file-meta"><span>{date}</span><span style="width:60px; text-align:right;">{size}</span></div><div class="actions"><button class="kebab-btn" onclick="toggleMenu(event, \'m-{f_html}\')">⋮</button><div class="dropdown-content" id="m-{f_html}">{admin_h}</div></div></div>'
            else:
                p_type = get_preview_type(f)
                
                # حل مشکل 404 در دانلود (اسلش‌ها دست‌نخورده باقی می‌مانند)
                dl_path = f"/{req_dir}/{f}".replace('//', '/')
                dl = urllib.parse.quote(dl_path, safe='/')
                
                p_type_str = p_type if p_type else 'download'
                p_click = f"handleItemClick('/download{dl}', '{p_type_str}', '{lock_id}')"
                
                share_badge = ""
                view_link_btn = ""
                if rel in link_map:
                    tk, data = link_map[rel][0]
                    pwd_hint = f" (Pass: {data.get('pwd')})" if isinstance(data, dict) and data.get('pwd') else ""
                    share_badge = f'<span style="color:var(--neon-red); font-size:10px; margin-left:8px; text-shadow:0 0 8px var(--neon-red-glow); white-space:nowrap;">● Shared{pwd_hint if role == "admin" else ""}</span>'
                    view_link_btn = f'<button class="action-accent" onclick="viewLink(\'{tk}\')">👁️ View Link</button>'
                        
                is_text = f.split('.')[-1].lower() in ['txt', 'md', 'py', 'json', 'html', 'css', 'js', 'conf', 'sh']
                
                if role == 'admin':
                    toggle_dl_btn = f'<button class="action-accent" onclick="toggleDl(\'{f_safe_js}\')">{"✅ Enable Download" if is_no_dl else "🚫 Disable Download"}</button>'
                    s_btns = f'{view_link_btn}<button class="action-accent" onclick="renewItem(\'{f_safe_js}\')">🔄 Renew Link</button><button class="action-red" onclick="unshareItem(\'{f_safe_js}\')">🚫 Unshare</button>' if share_badge else f'<button class="action-accent" onclick="shareItem(\'{f_safe_js}\')">🔗 Public Link</button><button class="action-accent" onclick="limitedShareItem(\'{f_safe_js}\')">⏳ Limited Link</button><button class="action-orange" onclick="pwdShareItem(\'{f_safe_js}\')">🔑 Secure Link</button>'
                    edit_btn = f'<button class="action-orange" onclick="editItem(\'{f_safe_js}\', \'{lock_id}\')">📝 Edit File</button>' if is_text else ""
                    admin_h = f'{toggle_dl_btn}{s_btns}{edit_btn}<button class="action-orange" onclick="lockItem(\'{f_safe_js}\')">🔒 Lock / Unlock</button><button class="action-orange" onclick="renameItem(\'{f_safe_js}\')">✏️ Rename</button><button class="action-accent" onclick="copyItem(\'{f_safe_js}\')">📄 Copy</button><button class="action-accent" onclick="moveItem(\'{f_safe_js}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f_safe_js}\')">🗑️ Delete</button>'
                else: 
                    admin_h = ''
                    
                dl_btn = f'<a href="/download{dl}?dl=1" class="btn btn-action" style="padding: 6px 12px; font-size: 11px;">Download</a>' if role == 'admin' or not is_no_dl else ''
                
                rows += f'<div class="file-item" data-name="{f_html}"><div class="file-info">{cb_html}<span style="font-size:18px; flex-shrink:0;">{get_icon(f, False)}</span><span onclick="{p_click}" class="file-name">{f_html}{lock_info}{share_badge}{stream_badge}</span></div><div class="file-meta"><span>{date}</span><span style="width:60px; text-align:right;">{size}</span></div><div class="actions">{dl_btn}<button class="kebab-btn" onclick="toggleMenu(event, \'m-{f_html}\')">⋮</button><div class="dropdown-content" id="m-{f_html}">{admin_h}</div></div></div>'
        
        uname_display = self.get_logged_username() or "Admin"
        role_badge = "⭐ Admin" if self.is_super_admin() else f"👤 {uname_display}"
        html_out = UI_HTML.replace('{site_name}', str(self.CONFIG.get('SITE_NAME', 'BLACK HUB'))) \
                          .replace('{role}', role_badge) \
                          .replace('{breadcrumbs}', str(bc)) \
                          .replace('{admin_top_btn}', str(select_all_btn + admin_btn)) \
                          .replace('{admin_log_btn}', str(admin_log_btn)) \
                          .replace('{disk_dashboard}', str(disk_html)) \
                          .replace('{admin_upload_area}', str(up_area)) \
                          .replace('{file_rows}', str(rows)) \
                          .replace('{current_dir}', str(req_dir))
                          
        self._send_resp(html_out)

    def do_POST(self):
        client_ip = self.get_client_ip()
        if check_ip(client_ip): self.send_error(403); return
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/login":
            l = int(self.headers.get('Content-Length', 0))
            body = urllib.parse.parse_qs(self.rfile.read(l).decode())
            username = body.get('username', [''])[0].strip()
            pwd = body.get('password', [''])[0]
            
            # Admin login
            if username == 'admin' and pwd == self.CONFIG['ADMIN_PWD']:
                clr_fail(client_ip)
                add_log(client_ip, f"Admin Login Successful")
                tk = hashlib.sha256(pwd.encode()).hexdigest()
                self.send_response(302)
                self.send_header("Set-Cookie", f"auth={tk}; Path=/; HttpOnly")
                self.send_header("Set-Cookie", f"auth_user=; Max-Age=0; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                # Multi-user login
                users = load_users()
                if username in users and users[username]['password'] == hashlib.sha256(pwd.encode()).hexdigest():
                    clr_fail(client_ip)
                    add_log(client_ip, f"User Login: {username}")
                    token = hashlib.sha256(f"{username}:{users[username]['password']}".encode()).hexdigest()
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"auth_user={token}; Path=/; HttpOnly")
                    self.send_header("Set-Cookie", f"auth=; Max-Age=0; Path=/; HttpOnly")
                    self.send_header("Location", "/")
                    self.end_headers()
                else:
                    max_fails = int(self.CONFIG.get('MAX_FAILS', 15))
                    rec_fail(client_ip, max_fails)
                    self.send_error(401)
                    return
                
        if self.get_role() != "admin": return
        
        if parsed.path == "/upload": 
            q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]
            curr = self.get_safe_path(q)
            # Quota check for regular users (not super admin)
            if not self.is_super_admin():
                uname = self.get_logged_username()
                users = load_users()
                if uname in users:
                    quota = users[uname].get('quota', 0)
                    if quota > 0:
                        used = get_user_used(self.CONFIG['UPLOAD_DIR'], uname)
                        content_len = int(self.headers.get('Content-Length', 0))
                        if used + content_len > quota:
                            self.send_response(413)
                            self.end_headers()
                            self.wfile.write(b"Storage quota exceeded!")
                            return
            self._handle_upload(curr)
            return
        
        elif parsed.path == "/api/change_pwd":
            # Any logged-in user can change their own password
            uname = self.get_logged_username()
            if not uname:
                self.send_response(403); self.end_headers(); return
            l = int(self.headers.get('Content-Length', 0))
            data = urllib.parse.parse_qs(self.rfile.read(l).decode())
            current_pwd = data.get('current_pwd', [''])[0]
            new_pwd     = data.get('new_pwd',     [''])[0]
            if not current_pwd or not new_pwd:
                self.send_response(400); self.end_headers(); self.wfile.write(b"Missing fields"); return

            if self.is_super_admin():
                # Super admin: verify against ADMIN_PWD in config
                if hashlib.sha256(current_pwd.encode()).hexdigest() != hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest():
                    self.send_response(200); self.end_headers(); self.wfile.write(b"WRONG"); return
                # Update config file
                lines = open(CONFIG_FILE, 'r', encoding='utf-8').readlines()
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    for line in lines:
                        if line.startswith('ADMIN_PWD='):
                            f.write(f'ADMIN_PWD={new_pwd}\n')
                        else:
                            f.write(line)
                # Reload config in handler
                FileHubHandler.CONFIG = load_config()
                add_log(client_ip, "Admin changed their password")
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
            else:
                # Regular user: verify against users.json
                users = load_users()
                if uname not in users:
                    self.send_response(403); self.end_headers(); return
                if users[uname]['password'] != hashlib.sha256(current_pwd.encode()).hexdigest():
                    self.send_response(200); self.end_headers(); self.wfile.write(b"WRONG"); return
                users[uname]['password']  = hashlib.sha256(new_pwd.encode()).hexdigest()
                users[uname]['plain_pwd'] = new_pwd
                save_users(users)
                add_log(client_ip, f"User {uname} changed their password")
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return

        elif parsed.path == "/api/users" and self.is_super_admin():
            l = int(self.headers.get('Content-Length', 0))
            data = urllib.parse.parse_qs(self.rfile.read(l).decode())
            act = data.get('action', [''])[0]
            uname = data.get('username', [''])[0].strip()
            
            if act == 'add':
                pwd = data.get('password', [''])[0]
                quota_mb = int(data.get('quota_mb', ['0'])[0])
                if not uname or not pwd:
                    self.send_response(400); self.end_headers(); self.wfile.write(b"Missing fields"); return
                users = load_users()
                if uname in users:
                    self.send_response(200); self.end_headers(); self.wfile.write(b"EXISTS"); return
                users[uname] = {
                    'password': hashlib.sha256(pwd.encode()).hexdigest(),
                    'plain_pwd': pwd,
                    'quota': quota_mb * 1024 * 1024,
                    'created': datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                save_users(users)
                get_user_dir(self.CONFIG['UPLOAD_DIR'], uname)  # create dir
                add_log(client_ip, f"Admin Added User: {uname}")
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
                
            elif act == 'delete':
                users = load_users()
                if uname in users:
                    del users[uname]
                    save_users(users)
                    add_log(client_ip, f"Admin Deleted User: {uname}")
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
                
            elif act == 'edit':
                quota_mb = int(data.get('quota_mb', ['0'])[0])
                new_pwd = data.get('password', [''])[0]
                users = load_users()
                if uname in users:
                    users[uname]['quota'] = quota_mb * 1024 * 1024
                    if new_pwd:
                        users[uname]['password'] = hashlib.sha256(new_pwd.encode()).hexdigest()
                        users[uname]['plain_pwd'] = new_pwd
                    save_users(users)
                    add_log(client_ip, f"Admin Edited User: {uname}")
                self.send_response(200); self.end_headers(); self.wfile.write(b"OK"); return
            
            self.send_response(400); self.end_headers(); return
            
        elif parsed.path == "/action":
            l = int(self.headers.get('Content-Length', 0))
            data = urllib.parse.parse_qs(self.rfile.read(l).decode())
            
            q = data.get('dir', [''])[0]
            curr = self.get_safe_path(q)
            
            act = data.get('action',[''])[0]
            target = data.get('target',[''])[0]
            
            if act == 'get_logs':
                content = ""
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r', encoding='utf-8') as f: content = f.read()
                self.send_response(200); self.end_headers(); self.wfile.write(content.encode('utf-8')); return

            if act == 'get_tree':
                base = os.path.abspath(self.CONFIG['UPLOAD_DIR'])
                dirs = ["/"]
                for root, d_names, _ in os.walk(base):
                    for d in d_names:
                        full = os.path.join(root, d)
                        rel = os.path.relpath(full, base).replace('\\', '/')
                        dirs.append("/" + rel)
                dirs.sort()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps(dirs).encode()); return

            if act == 'clear_logs':
                open(LOG_FILE, 'w').close(); add_log(client_ip, "Logs cleared"); self.send_response(200); self.end_headers(); return
            
            tp = os.path.join(curr, target); rel = self.get_rel(tp)
            
            if act in ['batch_delete', 'batch_move', 'batch_copy']:
                targets = data.get('targets', [''])[0].split('|')
                dest = self.get_safe_path(data.get('dest', [''])[0]) if act in ['batch_move', 'batch_copy'] else ""
                for tgt in targets:
                    if not tgt: continue
                    tp_multi = os.path.join(curr, tgt)
                    if act == 'batch_delete' and os.path.exists(tp_multi):
                        shutil.rmtree(tp_multi) if os.path.isdir(tp_multi) else os.remove(tp_multi)
                    elif act in ['batch_move', 'batch_copy'] and os.path.exists(tp_multi):
                        final = os.path.join(dest, tgt)
                        if act == 'batch_move': shutil.move(tp_multi, final)
                        else: (shutil.copytree if os.path.isdir(tp_multi) else shutil.copy2)(tp_multi, final)
                self.send_response(200); self.end_headers(); return
            
            if act == 'mkdir': os.makedirs(tp, exist_ok=True)
            elif act == 'mkfile': 
                if not os.path.exists(tp): open(tp, 'w', encoding='utf-8').close()
            elif act == 'delete' and os.path.exists(tp): 
                shutil.rmtree(tp) if os.path.isdir(tp) else os.remove(tp)
            elif act == 'rename' and os.path.exists(tp):
                new_name = data.get('new_name', [''])[0]; new_tp = os.path.join(curr, new_name)
                if new_name and not os.path.exists(new_tp):
                    os.rename(tp, new_tp); new_rel = self.get_rel(new_tp)
                    locks = load_json(LOCKS_FILE); l_changed = False; n_locks = {}
                    for k, v in locks.items():
                        if k == rel or k.startswith(rel + '/'): n_locks[new_rel + k[len(rel):]] = v; l_changed = True
                        else: n_locks[k] = v
                    if l_changed: save_json(n_locks, LOCKS_FILE)
                    lns = load_json(LINKS_FILE); ln_changed = False
                    for tk, l_data in lns.items():
                        tgt = l_data.get('target') if isinstance(l_data, dict) else l_data
                        if tgt == rel or tgt.startswith(rel + '/'):
                            n_tgt = new_rel + tgt[len(rel):]
                            if isinstance(l_data, dict): lns[tk]['target'] = n_tgt
                            else: lns[tk] = n_tgt
                            ln_changed = True
                    if ln_changed: save_json(lns, LINKS_FILE)
            elif act in ['move', 'copy']:
                dest = self.get_safe_path(data.get('dest', [''])[0])
                if os.path.exists(tp):
                    final = os.path.join(dest, target)
                    if act == 'move': shutil.move(tp, final)
                    else: (shutil.copytree if os.path.isdir(tp) else shutil.copy2)(tp, final)
            elif act == 'save_text' and os.path.isfile(tp):
                with open(tp, 'w', encoding='utf-8') as f: f.write(data.get('content', [''])[0])
            elif act == 'lock_item' and os.path.exists(tp):
                locks = load_json(LOCKS_FILE); pwd = data.get('pwd', [''])[0]
                if pwd: locks[rel] = pwd
                else: locks.pop(rel, None)
                save_json(locks, LOCKS_FILE)
            elif act == 'toggle_dl' and os.path.isfile(tp):
                ndl = load_json(NODL_FILE)
                if rel in ndl: del ndl[rel]
                else: ndl[rel] = True
                save_json(ndl, NODL_FILE)
            elif act in ['share', 'share_limit', 'share_pwd', 'renew'] and os.path.isfile(tp):
                lns = load_json(LINKS_FILE)
                if act == 'renew': lns = {k:v for k,v in lns.items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                
                c_path = data.get('custom_path', [''])[0].strip()
                c_path = re.sub(r'[^a-zA-Z0-9_-]', '', c_path) 
                
                if c_path:
                    if c_path in lns and act != 'renew':
                        self.send_response(200); self.end_headers(); self.wfile.write(b"EXISTS"); return
                    tk = c_path
                else:
                    tk = str(uuid.uuid4())[:8]
                    while tk in lns: tk = str(uuid.uuid4())[:8]
                
                limit = int(data.get('limit', ['-1'])[0]) if act == 'share_limit' else -1
                lns[tk] = {'target': rel, 'limit': limit, 'pwd': data.get('pwd', [''])[0] if act == 'share_pwd' else ""}
                save_json(lns, LINKS_FILE); self.send_response(200); self.end_headers(); self.wfile.write(f"/p/{tk}".encode()); return
            elif act == 'unshare':
                lns = load_json(LINKS_FILE)
                lns = {k:v for k,v in lns.items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                save_json(lns, LINKS_FILE)
                
            self.send_response(200); self.end_headers()

    def _handle_upload(self, curr):
        try:
            client_ip = self.get_client_ip()
            content_type = self.headers.get('Content-Type')
            if not content_type or 'boundary=' not in content_type:
                self.send_error(400)
                return
                
            boundary = content_type.split('boundary=')[1].encode()
            remainbytes = int(self.headers.get('Content-Length', 0))
            
            while remainbytes > 0:
                line = self.rfile.readline()
                remainbytes -= len(line)
                if boundary in line:
                    break
                    
            while remainbytes > 0:
                filename = None
                
                while remainbytes > 0:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if line == b'\r\n':
                        break
                    fn = re.findall(r'filename="(.*?)"', line.decode('utf-8', 'ignore'))
                    if fn:
                        filename = fn[0]
                        
                if not filename:
                    while remainbytes > 0:
                        line = self.rfile.readline()
                        remainbytes -= len(line)
                        if boundary in line:
                            break
                    if b'--' + boundary + b'--' in line:
                        break
                    continue
                    
                out_path = os.path.join(curr, filename)
                with open(out_path, 'wb') as f:
                    preline = self.rfile.readline()
                    remainbytes -= len(preline)
                    while remainbytes > 0:
                        line = self.rfile.readline()
                        remainbytes -= len(line)
                        if boundary in line:
                            if preline.endswith(b'\r\n'):
                                f.write(preline[:-2])
                            elif preline.endswith(b'\n'):
                                f.write(preline[:-1])
                            else:
                                f.write(preline)
                            break
                        else:
                            f.write(preline)
                            preline = line
                            
                add_log(client_ip, f"Uploaded File: {filename}")
                if b'--' + boundary + b'--' in line:
                    break
                    
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            print("Upload Error:", e)
            self.send_error(500)

    def _send_file(self, p, dl=False, name=None):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(p)))
        if dl: self.send_header("Content-Disposition", f'attachment; filename="{name or os.path.basename(p)}"')
        self.end_headers()
        with open(p, "rb") as f: shutil.copyfileobj(f, self.wfile)
        
    def _send_resp(self, h):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(h.encode('utf-8'))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('cmd', choices=['setup', 'run'])
    args = p.parse_args()
    
    if args.cmd == "setup":
        print("\n--- HUB SETUP ---")
        sn = input("Site Name [BLACK HUB]: ") or "BLACK HUB"
        ap = input("Admin Password [admin]: ") or "admin"
        gp = input("Guest Password [1234]: ") or "1234"
        pt = input("Port [5000]: ") or "5000"
        sd = input("Storage Path [./uploads]: ") or "./uploads"
        mf = input("Max Failed Logins before Ban [15]: ") or "15"
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: 
            f.write(f"SITE_NAME={sn}\nADMIN_PWD={ap}\nGUEST_PWD={gp}\nPORT={pt}\nUPLOAD_DIR={sd}\nMAX_FAILS={mf}\n")
            
        if not os.path.exists(sd): 
            os.makedirs(sd)
            
        print(f"\n[✔] Setup Complete! Run 'python3 hub.py run' to start.")
        
    elif args.cmd == "run":
        socketserver.TCPServer.allow_reuse_address = True
        cfg = load_config()
        if not cfg: 
            print("[!] No config found! Run Setup first.")
            return
            
        threading.Thread(target=calculate_dir_size_bg, args=(cfg['UPLOAD_DIR'],), daemon=True).start()
            
        FileHubHandler.CONFIG = cfg
        with socketserver.ThreadingTCPServer(("0.0.0.0", int(cfg['PORT'])), FileHubHandler) as h:
            print(f"[*] Hub is running on port {cfg['PORT']}...")
            h.serve_forever()

if __name__ == "__main__": 
    main()
