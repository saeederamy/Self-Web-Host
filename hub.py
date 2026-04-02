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

CONFIG_FILE = "fileserver.conf"
LINKS_FILE = "public_links.json"
LOCKS_FILE = "folder_locks.json"
LOG_FILE = "access_log.txt"
BLOCK_FILE = "ip_blocks.json"
NODL_FILE = "no_download.json"

# --- سیستم کش برای سرعت بخشیدن به لود سایت ---
_DIR_SIZE_CACHE = {'time': 0, 'size': 0}

def get_hub_size(path):
    global _DIR_SIZE_CACHE
    now = time.time()
    # آپدیت حجم کل سرور هر 15 ثانیه یک‌بار تا سایت کند نشود
    if now - _DIR_SIZE_CACHE['time'] < 15: 
        return _DIR_SIZE_CACHE['size']
    sz = 0
    try:
        for r, _, fs in os.walk(path):
            for n in fs:
                fp = os.path.join(r, n)
                if not os.path.islink(fp): 
                    sz += os.path.getsize(fp)
        _DIR_SIZE_CACHE['time'] = now
        _DIR_SIZE_CACHE['size'] = sz
    except: 
        pass
    return _DIR_SIZE_CACHE['size']

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
    b = load_json(BLOCK_FILE)
    return ip in b and b[ip].get('block_until', 0) > time.time()

def rec_fail(ip, mx):
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
    if not os.path.exists(CONFIG_FILE): 
        return None
    cfg = {}
    for line in open(CONFIG_FILE, "r", encoding="utf-8"):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            cfg[k] = v
    return cfg

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: 
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def is_locked(t_rel, l_path): 
    return t_rel == l_path or t_rel.startswith(l_path + "/")

COMMON_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&display=swap');

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

[data-theme='black-blue'] { 
    --bg-dark: #0a0a0f; 
    --bg-gradient: radial-gradient(circle at 50% 0%, #1a1a2e 0%, #0a0a0f 70%); 
    --accent: #3b82f6; 
    --accent-glow: rgba(59, 130, 246, 0.4); 
    --accent-text: #ffffff; 
}

[data-theme='black-red'] { 
    --bg-dark: #0f0000; 
    --bg-gradient: radial-gradient(circle at 50% 0%, #2a0808 0%, #0f0000 70%); 
    --accent: #ef4444; 
    --accent-glow: rgba(239, 68, 68, 0.4); 
    --accent-text: #ffffff; 
}

[data-theme='pure-black'] { 
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

[data-theme='light'] { 
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
    font-family: 'Inter', system-ui, sans-serif; 
    background: var(--bg-dark); 
    background-image: var(--bg-gradient); 
    color: var(--text-main); 
    margin: 0; 
    min-height: 100vh; 
    transition: background 0.3s ease, color 0.3s ease; 
}

.glass-box { 
    background: var(--glass-bg); 
    backdrop-filter: blur(16px); 
    -webkit-backdrop-filter: blur(16px); 
    border: 1px solid var(--glass-border); 
    border-radius: 16px; 
    box-shadow: var(--glass-shadow); 
    transition: 0.3s; 
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); border-radius: 10px; }
::-webkit-scrollbar-thumb { background: var(--glass-border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
"""

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{site_name}</title>
<script>document.documentElement.setAttribute('data-theme', localStorage.getItem('hub_theme') || 'black-white');</script>
<style>
""" + COMMON_STYLE + """
.header { background: var(--glass-bg); backdrop-filter: blur(20px); border-bottom: 1px solid var(--glass-border); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; }
.logo { font-size: 22px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; }
.badge { border: 1px solid var(--accent); padding: 4px 14px; border-radius: 50px; font-size: 11px; font-weight: 600; color: var(--accent); background: rgba(128,128,128,0.1); text-transform: uppercase; white-space: nowrap; }
.theme-select { background: transparent; color: var(--text-main); border: 1px solid var(--glass-border); padding: 6px; border-radius: 8px; outline: none; }
.theme-select option { background: var(--bg-dark); color: var(--text-main); }
.logout-link { color: var(--neon-red); text-decoration: none; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(239,68,68,0.3); transition: 0.3s; white-space: nowrap; }
.logout-link:hover { background: var(--neon-red); color: #fff; }

.container { max-width: 1200px; margin: 0 auto; padding: 30px 25px; }
.search-box { width: 100%; background: var(--input-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 16px 20px; color: var(--text-main); margin-bottom: 25px; box-sizing: border-box; }
.file-item { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--glass-border); border-left: 2px solid transparent; transition: 0.2s; }
.file-item:hover { background: var(--glass-border); border-left: 2px solid var(--accent); }
.file-info { display: flex; align-items: center; gap: 15px; flex: 1; min-width: 0; }
.file-name { font-size: 15px; font-weight: 500; color: var(--text-main); text-decoration: none; word-break: break-word; cursor: pointer; transition: 0.2s; }
.file-name:hover { color: var(--accent); }
.actions { display: flex; gap: 12px; align-items: center; }

.btn { padding: 8px 16px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; border: 1px solid var(--glass-border); background: var(--glass-bg); color: var(--text-main); transition: 0.3s; white-space: nowrap;}
.btn:hover { background: var(--glass-border); transform: translateY(-2px); }
.btn-action { background: rgba(128,128,128,0.1); color: var(--accent); border-color: var(--accent-glow); }
.kebab-btn { background: transparent; border: 1px solid var(--glass-border); color: var(--text-main); cursor: pointer; font-size: 18px; width: 36px; height: 36px; border-radius: 10px; }

.dropdown-content { display: none; position: absolute; right: 24px; top: 55px; background: var(--bg-dark); backdrop-filter: blur(20px); border: 1px solid var(--glass-border); min-width: 200px; border-radius: 12px; z-index: 100; box-shadow: var(--glass-shadow); padding: 8px; }
.dropdown-content button { width: 100%; padding: 12px 16px; text-align: left; background: transparent; border: none; color: var(--text-muted); font-size: 13px; cursor: pointer; border-radius: 8px; }
.dropdown-content button:hover { background: var(--glass-border); color: var(--text-main); }
.dropdown-content button.action-red:hover { background: rgba(239, 68, 68, 0.15); color: var(--neon-red); border-left: 2px solid var(--neon-red); }
.dropdown-content button.action-orange:hover { background: rgba(249, 115, 22, 0.15); color: var(--neon-orange); border-left: 2px solid var(--neon-orange); }

.show { display: block; }
.modal { display: none; position: fixed; z-index: 2000; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(15px); justify-content: center; align-items: center; }
.modal-content { width: 90%; height: 85%; max-width: 1000px; position: relative; display: flex; justify-content: center; align-items: center; }
.tree-item { padding: 12px 15px; cursor: pointer; border-radius: 8px; color: var(--text-muted); font-size: 14px; margin-bottom: 4px; }
.tree-item:hover { background: var(--glass-border); color: var(--text-main); }
.tree-item.selected { background: rgba(128,128,128,0.15); color: var(--accent); border: 1px solid var(--accent-glow); }
iframe, video, img { border-radius: 12px; border: 1px solid var(--glass-border); max-width: 100%; max-height: 100%; background: rgba(0,0,0,0.5); }

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
}
</style>
</head>
<body>
    <div class="header">
        <div class="logo">{site_name}</div>
        <div style="display:flex;gap:15px;align-items:center">
            <select id="themeSelector" class="theme-select" onchange="changeTheme(this.value)">
                <option value="black-white">Black & White</option>
                <option value="black-blue">Black & Blue</option>
                <option value="black-red">Black & Red</option>
                <option value="pure-black">Pure Black</option>
            </select>
            <span class="badge">{role}</span>
            <a href="/logout" class="logout-link">Logout</a>
        </div>
    </div>
    
    <div class="container">
        <input type="text" id="search" class="search-box glass-box" placeholder="🔍 Search files..." onkeyup="doSearch()">
        <div style="display:flex;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <div style="font-size:14px;color:var(--text-muted);word-break:break-all;">{breadcrumbs}</div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;">{admin_top_btn}{admin_log_btn}</div>
        </div>
        {disk_dashboard}
        {admin_upload_area}
        <div class="file-list glass-box">{file_rows}</div>
    </div>
    
    <div id="batch-bar" class="glass-box" style="display:none;position:fixed;bottom:25px;left:50%;transform:translateX(-50%);z-index:1001;padding:15px 25px;align-items:center;gap:15px;border-color:var(--accent);">
        <span id="batch-count" style="font-weight:900;color:var(--accent);font-size:14px;min-width:80px;text-align:center;">0 selected</span>
        <button class="btn action-accent" onclick="batchCopy()">📄 Copy</button>
        <button class="btn action-accent" onclick="batchMove()">✂️ Move</button>
        <button class="btn action-red" style="color:var(--neon-red);border-color:var(--neon-red)" onclick="batchDelete()">🗑️ Delete</button>
    </div>
    
    <div id="previewModal" class="modal">
        <div class="modal-content">
            <span style="position:absolute;top:-40px;right:0;color:#fff;font-size:35px;cursor:pointer" onclick="closePreview()">&times;</span>
            <div id="previewBody" style="width:100%;height:100%;display:flex;justify-content:center;align-items:center"></div>
        </div>
    </div>
    
    <div id="treeModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column;padding:25px;max-width:500px;height:75%;">
            <h3 id="tree-title" style="margin:0 0 20px 0;color:var(--text-main);border-bottom:1px solid var(--glass-border);padding-bottom:15px;width:100%;">Select Destination</h3>
            <div id="tree-list" style="flex:1;width:100%;overflow-y:auto;background:var(--input-bg);border:1px solid var(--glass-border);border-radius:12px;padding:15px;"></div>
            <div style="margin-top:20px;display:flex;gap:12px;width:100%;justify-content:flex-end">
                <button class="btn" onclick="document.getElementById('treeModal').style.display='none'">Cancel</button>
                <button class="btn btn-action" onclick="confirmTreeAction()">Confirm</button>
            </div>
        </div>
    </div>
    
    <div id="logModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column;padding:25px;max-width:800px;height:85%;">
            <div style="display:flex;justify-content:space-between;width:100%;margin-bottom:20px">
                <h3 style="margin:0;color:var(--text-main)">System Logs</h3>
                <div style="display:flex;gap:12px">
                    <a href="/download_logs" class="btn">📥 Download</a>
                    <button class="btn" style="color:var(--neon-red)" onclick="clearLogs()">🗑️ Clear</button>
                </div>
            </div>
            <textarea readonly id="log-viewer" style="width:100%;height:100%;background:rgba(0,0,0,0.8);color:#10b981;border-radius:12px;padding:20px;outline:none;resize:none;"></textarea>
            <button class="btn" style="margin-top:20px" onclick="document.getElementById('logModal').style.display='none'">Close</button>
        </div>
    </div>
    
    <div id="editModal" class="modal">
        <div class="modal-content glass-box" style="flex-direction:column;padding:25px;max-width:800px;height:85%;">
            <h3 id="edit-name" style="color:var(--text-main);border-bottom:1px solid var(--glass-border);padding-bottom:15px;width:100%;"></h3>
            <textarea id="edit-box" style="width:100%;height:100%;background:rgba(0,0,0,0.8);color:#f8fafc;padding:20px;border-radius:12px;outline:none;border:1px solid var(--neon-orange);"></textarea>
            <div style="margin-top:20px;display:flex;gap:12px;justify-content:flex-end">
                <button class="btn" onclick="document.getElementById('editModal').style.display='none'">Cancel</button>
                <button class="btn action-orange" onclick="saveEdit()">💾 Save Changes</button>
            </div>
        </div>
    </div>

    <script>
        const currentDir = "{current_dir}";
        
        document.getElementById('themeSelector').value = localStorage.getItem('hub_theme') || 'black-white';
        function changeTheme(t) {
            document.documentElement.setAttribute('data-theme', t); 
            localStorage.setItem('hub_theme', t); 
        }
        
        let selectedFiles = [];
        
        function toggleSelection(e) {
            e.stopPropagation(); 
            updateBatchBar(); 
        }
        
        function toggleAll(e) {
            let checkboxes = document.querySelectorAll('.file-cb');
            checkboxes.forEach(cb => cb.checked = e.target.checked); 
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
            if(confirm('Delete ' + selectedFiles.length + ' items permanently?')) {
                fetch('/action', {
                    method: 'POST',
                    body: new URLSearchParams({
                        action: 'batch_delete',
                        targets: selectedFiles.join('|'),
                        dir: currentDir
                    })
                }).then(() => location.reload());
            }
        }
        
        function batchMove() { openTreeModal('batch_move', selectedFiles.join('|')); }
        function batchCopy() { openTreeModal('batch_copy', selectedFiles.join('|')); }
        
        function handleItemClick(u, t, lId) {
            if(lId) {
                document.cookie = "lock_" + lId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 This item is Locked. Password:");
                if(p) {
                    document.cookie = "lock_" + lId + "=" + p + ";path=/"; 
                } else {
                    return;
                }
            }
            if(t === 'download') window.location.href = u; 
            else openPreview(u, t);
        }
        
        function doSearch() {
            let q = document.getElementById('search').value.toLowerCase();
            document.querySelectorAll('.file-item').forEach(i => {
                let n = i.getAttribute('data-name').toLowerCase();
                i.style.display = (n.includes(q) || n === '..') ? 'flex' : 'none';
            });
        }
        
        function toggleMenu(e, id) {
            e.stopPropagation();
            document.querySelectorAll('.dropdown-content').forEach(d => {
                if(d.id !== id) d.classList.remove('show');
            });
            document.getElementById(id).classList.toggle('show');
        }
        
        window.onclick = (e) => {
            if(!e.target.closest('.dropdown-content') && !e.target.matches('.kebab-btn')) {
                document.querySelectorAll('.dropdown-content').forEach(d => d.classList.remove('show'));
            }
        };
        
        function openPreview(u, t) {
            let b = document.getElementById('previewBody'); 
            b.innerHTML = '';
            document.getElementById('previewModal').style.display = 'flex';
            
            if(t === 'image') b.innerHTML = `<img src="${u}" oncontextmenu="return false;">`;
            else if(t === 'video') b.innerHTML = `<video controls controlsList="nodownload" autoplay style="width:100%" oncontextmenu="return false;"><source src="${u}"></video>`;
            else if(t === 'audio') b.innerHTML = `<audio controls controlsList="nodownload" autoplay oncontextmenu="return false;"><source src="${u}"></audio>`;
            else if(t === 'pdf') b.innerHTML = `<iframe src="${u}#toolbar=0" style="width:100%;height:100%;background:#fff" oncontextmenu="return false;"></iframe>`;
            else window.location.href = u + "&dl=1";
        }
        
        function closePreview() {
            document.getElementById('previewModal').style.display = 'none'; 
            document.getElementById('previewBody').innerHTML = ''; 
        }
        
        function openLogs() {
            document.getElementById('logModal').style.display = 'flex';
            document.getElementById('log-viewer').value = 'Loading...';
            fetch('/action', {
                method: 'POST',
                body: new URLSearchParams({action: 'get_logs'})
            }).then(r => r.text()).then(t => document.getElementById('log-viewer').value = t);
        }
        
        let treeAct = '', treeTgt = '', treeSel = null;
        
        function openTreeModal(a, t) {
            treeAct = a; 
            treeTgt = t; 
            treeSel = null;
            
            let actionText = a.includes('move') ? '✂️ Move ' : '📄 Copy ';
            let targetText = a.includes('batch_') ? selectedFiles.length + ' items' : t;
            
            document.getElementById('tree-title').innerText = actionText + targetText + " to...";
            document.getElementById('treeModal').style.display = 'flex';
            document.getElementById('tree-list').innerHTML = '<div style="color:var(--accent);text-align:center;padding:30px;">Scanning Directories...</div>';
            
            fetch('/action', {
                method: 'POST',
                body: new URLSearchParams({action: 'get_tree'})
            }).then(r => r.json()).then(ds => {
                let h = '';
                ds.forEach(d => {
                    let pad = d === '/' ? 0 : (d.split('/').length - 1) * 20;
                    let n = d === '/' ? 'Root Directory ( / )' : d.split('/').pop();
                    h += `<div class="tree-item" style="padding-left:${pad+15}px" onclick="selectTreeItem(this,'${d}')">📁 ${n}</div>`;
                });
                document.getElementById('tree-list').innerHTML = h;
            });
        }
        
        function selectTreeItem(el, p) {
            document.querySelectorAll('.tree-item').forEach(i => i.classList.remove('selected'));
            el.classList.add('selected');
            treeSel = p === '/' ? '' : p.substring(1);
        }
        
        function confirmTreeAction() {
            if(treeSel === null) return alert('Select a destination folder first!');
            let params = { action: treeAct, dir: currentDir, dest: treeSel };
            
            if(treeAct.startsWith('batch_')) {
                params.targets = treeTgt;
            } else {
                params.target = treeTgt;
            }
            
            fetch('/action', {
                method: 'POST',
                body: new URLSearchParams(params)
            }).then(() => location.reload());
        }
        
        function callAct(a, t, e = {}) {
            let p = new URLSearchParams({action: a, target: t, dir: currentDir});
            for(let k in e) p.append(k, e[k]);
            return fetch('/action', {method: 'POST', body: p}).then(() => location.reload());
        }
        
        function clearLogs() { if(confirm('Clear all system logs?')) callAct('clear_logs',''); }
        function createFolder() { let n = prompt("New Folder Name:"); if(n) callAct('mkdir',n); }
        function createFile() { let n = prompt("New File Name:"); if(n) callAct('mkfile',n); }
        function deleteItem(n) { if(confirm('Permanently delete ' + n + '?')) callAct('delete',n); }
        function renameItem(n) { let nn = prompt("Rename to:", n); if(nn && nn !== n) callAct('rename', n, {new_name: nn}); }
        function lockItem(n) { let p = prompt("Set Lock Password (leave empty to unlock):"); if(p !== null) callAct('lock_item', n, {pwd: p}); }
        function toggleDl(n) { callAct('toggle_dl', n); }
        
        function askPath(a, t, e = {}) {
            let cp = prompt("Enter custom link path (leave empty for random):\\nOnly letters, numbers, dash, underscore allowed.", "");
            if(cp === null) return;
            
            let p = {action: a, target: t, dir: currentDir, custom_path: cp};
            Object.assign(p, e);
            
            fetch('/action', {
                method: 'POST',
                body: new URLSearchParams(p)
            }).then(r => r.text()).then(l => {
                if(l === "EXISTS") alert("⚠️ This custom path already exists! Please try another one.");
                else { prompt("Link created successfully:", window.location.origin + l); location.reload(); }
            });
        }
        
        function shareItem(n) { askPath('share', n); }
        function limitedShareItem(n) { let l = prompt("Max Downloads:", "1"); if(l) askPath('share_limit', n, {limit: l}); }
        function pwdShareItem(n) { let p = prompt("Set Link Password:"); if(p) askPath('share_pwd', n, {pwd: p}); }
        function renewItem(n) { if(confirm('Generate a new link for this file? (Old link will expire)')) askPath('renew', n); }
        function unshareItem(n) { callAct('unshare', n); }
        function viewLink(tk) { prompt("Current Shared Link:", window.location.origin + "/p/" + tk); }
        
        function editItem(n, lId) {
            if(lId) {
                document.cookie = "lock_" + lId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 This item is Locked. Password:");
                if(p) document.cookie = "lock_" + lId + "=" + p + ";path=/"; 
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
            let targetFile = document.getElementById('edit-box').getAttribute('data-target');
            let newContent = document.getElementById('edit-box').value;
            callAct('save_text', targetFile, {content: newContent}); 
        }
        
        // --- Upload Logic ---
        const dz = document.getElementById('drop-zone');
        
        if(dz) {
            let fileInput = document.getElementById('file-input');
            let dropText = document.getElementById('drop-text');
            let selectedFilesDiv = document.getElementById('selected-files');
            let btnStart = document.getElementById('btn-start-upload');
            let btnPublish = document.getElementById('btn-confirm-publish');
            let pendingFiles = [];
            
            dz.onclick = (e) => {
                if(e.target !== btnStart && e.target !== btnPublish && !selectedFilesDiv.contains(e.target)) {
                    fileInput.click();
                }
            };
            
            dz.ondragover = (e) => {
                e.preventDefault();
                dz.style.borderColor = "var(--accent)";
                dz.style.background = "rgba(128,128,128,0.1)";
            };
            
            dz.ondragleave = (e) => {
                e.preventDefault();
                dz.style.borderColor = "var(--glass-border)";
                dz.style.background = "transparent";
            };
            
            dz.ondrop = (e) => {
                e.preventDefault();
                dz.style.borderColor = "var(--glass-border)";
                dz.style.background = "transparent";
                if(e.dataTransfer.files.length > 0) {
                    pendingFiles = Array.from(e.dataTransfer.files);
                    showPendingFiles();
                }
            };
            
            fileInput.onchange = (e) => {
                if(e.target.files.length > 0) {
                    pendingFiles = Array.from(e.target.files);
                    showPendingFiles();
                }
            };
            
            function showPendingFiles() {
                dropText.style.display = 'none';
                selectedFilesDiv.style.display = 'block';
                btnStart.style.display = 'block';
                btnPublish.style.display = 'none';
                document.getElementById('progress-wrapper').style.display = 'none';
                document.getElementById('progress-bar').style.width = '0%';
                
                let listHtml = pendingFiles.map(f => {
                    let sizeMB = (f.size / 1048576).toFixed(2);
                    return `📄 ${f.name} <span style="color:var(--text-muted)">(${sizeMB} MB)</span>`;
                }).join('<br>');
                
                selectedFilesDiv.innerHTML = listHtml;
            }
            
            btnStart.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                if(pendingFiles.length === 0) return;
                
                btnStart.style.pointerEvents = 'none';
                btnStart.innerText = '⏳ Uploading... Please wait';
                selectedFilesDiv.style.opacity = '0.5';
                
                const fd = new FormData();
                for(let f of pendingFiles) {
                    fd.append('file', f);
                }
                
                document.getElementById('progress-wrapper').style.display = 'block';
                
                const xhr = new XMLHttpRequest();
                xhr.open('POST', '/upload?dir=' + encodeURIComponent(currentDir), true);
                
                xhr.upload.onprogress = (ev) => {
                    if(ev.lengthComputable) {
                        let percent = Math.round((ev.loaded / ev.total) * 100);
                        document.getElementById('progress-bar').style.width = percent + '%';
                        document.getElementById('progress-bar').style.boxShadow = "0 0 15px var(--accent)";
                    }
                };
                
                xhr.onload = () => {
                    btnStart.style.display = 'none';
                    btnPublish.style.display = 'block';
                };
                
                xhr.send(fd);
            };
            
            btnPublish.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                location.reload();
            };
        }
    </script>
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        body { 
            display: flex; justify-content: center; align-items: center; 
            height: 100vh; margin: 0; background: #050505; font-family: 'Inter', sans-serif; 
        }
        
        .login-card { 
            padding: 40px; width: 90%; max-width: 340px; text-align: center; 
            background: rgba(20,20,20,0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; 
        }
        
        h2 { color: #fff; letter-spacing: 2px; }
        
        input { 
            width: 100%; padding: 16px; margin: 0 0 25px 0; 
            background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.2); 
            color: white; border-radius: 12px; box-sizing: border-box; outline: none; 
            text-align: center; letter-spacing: 4px; 
        }
        
        button { 
            width: 100%; padding: 16px; background: #fff; color: #000; border: none; 
            border-radius: 12px; cursor: pointer; font-weight: 800; text-transform: uppercase; 
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>{site_name}</h2>
        <form method="POST" action="/login">
            <input type="password" name="password" placeholder="••••••••" required autofocus>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

def get_icon(f, is_d):
    if is_d: return "📁"
    ext = f.split('.')[-1].lower()
    if ext in ['mp4', 'mkv', 'mov']: return "🎬"
    if ext in ['mp3', 'wav']: return "🎵"
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']: return "🖼️"
    if ext in ['pdf']: return "📕"
    if ext in ['zip', 'rar', '7z', 'tar', 'gz']: return "📦"
    if ext in ['py', 'cpp', 'html', 'js', 'css', 'sql', 'sh', 'json']: return "💻"
    return "📄"

def get_preview_type(f):
    ext = f.split('.')[-1].lower()
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']: return 'image'
    if ext in ['mp4', 'webm']: return 'video'
    if ext in ['mp3', 'wav']: return 'audio'
    if ext in ['pdf']: return 'pdf'
    return None

class FileHubHandler(http.server.BaseHTTPRequestHandler):
    CONFIG = {}
    
    def get_role(self):
        ck = self.headers.get("Cookie", "")
        if f"auth={hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest()}" in ck: return "admin"
        if f"auth={hashlib.sha256(self.CONFIG['GUEST_PWD'].encode()).hexdigest()}" in ck: return "user"
        return None

    def get_safe_path(self, r_dir):
        base = os.path.abspath(self.CONFIG['UPLOAD_DIR'])
        t = os.path.abspath(os.path.join(base, r_dir.strip('/')))
        return t if t.startswith(base) else base

    def get_rel(self, p):
        r = os.path.relpath(p, os.path.abspath(self.CONFIG['UPLOAD_DIR'])).replace('\\', '/')
        return "" if r == "." else r

    def do_GET(self):
        if check_ip(self.client_address[0]): 
            return self._send_resp('<h1>🚫 BLOCKED</h1>')
            
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/download_logs" and self.get_role() == "admin":
            if os.path.exists(LOG_FILE): 
                return self._send_file(LOG_FILE, dl=True, name="access_log.txt")
            return self.send_error(404)
            
        if parsed.path.startswith("/p/"):
            tk = parsed.path.split("/p/")[1]
            lns = load_json(LINKS_FILE)
            if tk in lns:
                ld = lns[tk]
                t_rel = ld.get('target') if isinstance(ld, dict) else ld
                lim = ld.get('limit', -1) if isinstance(ld, dict) else -1
                pwd = ld.get('pwd', '') if isinstance(ld, dict) else ''
                
                if pwd:
                    if urllib.parse.parse_qs(parsed.query).get('pwd', [''])[0] != pwd:
                        return self._send_resp('<script>let p=prompt("Password:");if(p)window.location.href="?pwd="+p;</script>')
                        
                tgt = self.get_safe_path(t_rel)
                if os.path.isfile(tgt):
                    add_log(self.client_address[0], f"Pub Link DL: {t_rel}")
                    if lim > 0:
                        lns[tk]['limit'] -= 1
                        if lns[tk]['limit'] <= 0: del lns[tk]
                        save_json(lns, LINKS_FILE)
                    return self._send_file(tgt, dl=True)
            return self.send_error(404)
        
        role = self.get_role()
        if not role: 
            return self._send_resp(LOGIN_HTML.replace('{site_name}', self.CONFIG.get('SITE_NAME', 'HUB')))
        
        q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]
        curr = self.get_safe_path(q)
        rel_curr = self.get_rel(curr)
        
        if parsed.path.startswith("/zip/"):
            tgt = self.get_safe_path(urllib.parse.unquote(parsed.path[5:]))
            if not self.check_item_lock(self.get_rel(tgt)): return
            if os.path.isdir(tgt):
                tmp = tempfile.mktemp()
                shutil.make_archive(tmp, 'zip', tgt)
                self._send_file(tmp+'.zip', dl=True, name=os.path.basename(tgt)+".zip")
                os.remove(tmp+'.zip')
            return
            
        if parsed.path == "/": 
            if self.check_item_lock(rel_curr): 
                self._serve_ui(role, curr, q)
            
        elif parsed.path.startswith("/download/"):
            tgt = self.get_safe_path(urllib.parse.unquote(parsed.path[10:]))
            rel = self.get_rel(tgt)
            if not self.check_item_lock(rel): return
            
            is_dl = urllib.parse.parse_qs(parsed.query).get('dl', ['0'])[0] == '1'
            ndl = load_json(NODL_FILE)
            if role != 'admin' and rel in ndl and is_dl:
                return self._send_resp('<h1>👀 STREAM ONLY (Download Disabled)</h1>')

            if os.path.isfile(tgt): 
                add_log(self.client_address[0], f"DL/Stream: {rel}")
                self._send_file(tgt, dl=is_dl)
                
        elif parsed.path == "/logout":
            self.send_response(302)
            self.send_header("Set-Cookie", "auth=; Max-Age=0; Path=/;")
            self.send_header("Location", "/")
            self.end_headers()

    def check_item_lock(self, t_rel):
        if self.get_role() == 'admin': return True
        locks = load_json(LOCKS_FILE)
        for lp, lpwd in locks.items():
            if is_locked(t_rel, lp):
                h = hashlib.md5(lp.encode()).hexdigest()
                if f"lock_{h}={lpwd}" not in urllib.parse.unquote(self.headers.get('Cookie', '')):
                    self._send_resp(f'<script>let p=prompt("🔒 Locked:"); if(p){{ document.cookie="lock_{h}="+p+";path=/"; location.reload(); }}</script>')
                    return False
        return True

    def do_POST(self):
        if check_ip(self.client_address[0]): 
            return self.send_error(403)
            
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/login":
            pwd = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()).get('password', [''])[0]
            if pwd in [self.CONFIG['ADMIN_PWD'], self.CONFIG['GUEST_PWD']]:
                clr_fail(self.client_address[0])
                tk = hashlib.sha256(pwd.encode()).hexdigest()
                self.send_response(302)
                self.send_header("Set-Cookie", f"auth={tk}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
            else: 
                rec_fail(self.client_address[0], int(self.CONFIG.get('MAX_FAILS', 15)))
                self.send_error(401)
            return
                
        if self.get_role() != "admin": return
        q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]
        curr = self.get_safe_path(q)
        
        if parsed.path == "/upload": 
            return self._handle_upload(curr)
            
        elif parsed.path == "/action":
            d = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
            act, tgt = d.get('action',[''])[0], d.get('target',[''])[0]
            
            if act == 'get_logs':
                c = open(LOG_FILE, 'r', encoding='utf-8').read() if os.path.exists(LOG_FILE) else ""
                self.send_response(200)
                self.end_headers()
                self.wfile.write(c.encode())
                return
                
            if act == 'get_tree':
                b = os.path.abspath(self.CONFIG['UPLOAD_DIR']); dirs = ["/"]
                for r, dn, _ in os.walk(b):
                    for dp in dn: 
                        dirs.append("/" + os.path.relpath(os.path.join(r, dp), b).replace('\\', '/'))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(sorted(dirs)).encode())
                return

            if act == 'clear_logs':
                open(LOG_FILE, 'w').close()
                self.send_response(200)
                self.end_headers()
                return
            
            tp = os.path.join(curr, tgt)
            rel = self.get_rel(tp)
            
            if act in ['batch_delete', 'batch_move', 'batch_copy']:
                dest = self.get_safe_path(d.get('dest', [''])[0]) if act != 'batch_delete' else ""
                for t in d.get('targets', [''])[0].split('|'):
                    if not t: continue
                    tm = os.path.join(curr, t)
                    if act == 'batch_delete' and os.path.exists(tm):
                        shutil.rmtree(tm) if os.path.isdir(tm) else os.remove(tm)
                    elif act in ['batch_move', 'batch_copy'] and os.path.exists(tm):
                        f = os.path.join(dest, t)
                        if act == 'batch_move':
                            shutil.move(tm, f) 
                        else:
                            shutil.copytree(tm, f) if os.path.isdir(tm) else shutil.copy2(tm, f)
                self.send_response(200)
                self.end_headers()
                return
            
            if act == 'mkdir': 
                os.makedirs(tp, exist_ok=True)
            elif act == 'mkfile' and not os.path.exists(tp): 
                open(tp, 'w').close()
            elif act == 'delete' and os.path.exists(tp): 
                shutil.rmtree(tp) if os.path.isdir(tp) else os.remove(tp)
            elif act == 'rename' and os.path.exists(tp):
                nn = d.get('new_name', [''])[0]
                nt = os.path.join(curr, nn)
                if nn and not os.path.exists(nt): 
                    os.rename(tp, nt)
            elif act in ['move', 'copy'] and os.path.exists(tp):
                dest = os.path.join(self.get_safe_path(d.get('dest', [''])[0]), tgt)
                if act == 'move':
                    shutil.move(tp, dest)
                else:
                    shutil.copytree(tp, dest) if os.path.isdir(tp) else shutil.copy2(tp, dest)
            elif act == 'save_text' and os.path.isfile(tp):
                open(tp, 'w', encoding='utf-8').write(d.get('content', [''])[0])
            elif act == 'lock_item' and os.path.exists(tp):
                locks = load_json(LOCKS_FILE)
                pwd = d.get('pwd', [''])[0]
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
                if act == 'renew': 
                    lns = {k:v for k,v in lns.items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                
                cp = re.sub(r'[^a-zA-Z0-9_-]', '', d.get('custom_path', [''])[0].strip())
                if cp:
                    if cp in lns and act != 'renew': 
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b"EXISTS")
                        return
                    tk = cp
                else:
                    tk = str(uuid.uuid4())[:8]
                    while tk in lns: 
                        tk = str(uuid.uuid4())[:8]
                        
                lns[tk] = {
                    'target': rel, 
                    'limit': int(d.get('limit', ['-1'])[0]) if act == 'share_limit' else -1, 
                    'pwd': d.get('pwd', [''])[0] if act == 'share_pwd' else ""
                }
                save_json(lns, LINKS_FILE)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f"/p/{tk}".encode())
                return
            elif act == 'unshare':
                lns = {k:v for k,v in load_json(LINKS_FILE).items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                save_json(lns, LINKS_FILE)
                
            self.send_response(200)
            self.end_headers()

    def _serve_ui(self, role, curr, req_dir):
        pts = [p for p in req_dir.split('/') if p]
        bc = '<a href="/">Root</a>'
        acc = ""
        for p in pts: 
            acc += f"/{p}"
            bc += f' / <a href="/?dir={urllib.parse.quote(acc)}">{p}</a>'
        
        sa_btn = '<label style="color:var(--text-main);font-size:12px;background:var(--glass-bg);padding:6px;border-radius:8px;cursor:pointer;"><input type="checkbox" onchange="toggleAll(event)" style="accent-color:var(--accent);"> Select All</label>' if role == 'admin' else ''
        a_btn = '<button class="btn btn-action" onclick="createFolder()">+ Folder</button><button class="btn btn-action" onclick="createFile()">+ File</button>' if role == 'admin' else ''
        l_btn = '<button class="btn" style="color:var(--neon-green);" onclick="openLogs()">📜 Logs</button>' if role == 'admin' else ''
        
        up_a = '<div class="glass-box" id="drop-zone" style="padding:25px;text-align:center;margin-bottom:25px;cursor:pointer;border:2px dashed var(--glass-border);"><p id="drop-text" style="font-size:14px;font-weight:500;color:var(--text-muted);">☁️ Drag & Drop or click to select files</p><input type="file" id="file-input" hidden multiple><div id="selected-files" style="display:none;margin-top:15px;font-size:13px;max-height:100px;overflow-y:auto;text-align:left;padding:10px;background:rgba(0,0,0,0.3);border-radius:8px;"></div><button id="btn-start-upload" class="btn btn-action" style="display:none;margin-top:15px;width:100%;padding:12px;">🚀 Start Upload</button><button id="btn-confirm-publish" class="btn" style="display:none;margin-top:15px;width:100%;padding:12px;background:#10b981;color:white;border-color:#10b981;box-shadow:0 0 20px rgba(16, 185, 129, 0.4);">✅ Confirm & Publish</button><div id="progress-wrapper" style="display:none;height:4px;background:rgba(0,0,0,0.5);margin-top:15px;border-radius:10px;overflow:hidden;"><div id="progress-bar" style="width:0;height:100%;background:var(--accent);transition:width 0.2s;"></div></div></div>' if role == 'admin' else ''
        
        d_html = ""
        if role == 'admin':
            try:
                tot, usd, fre = shutil.disk_usage(self.CONFIG['UPLOAD_DIR'])
                sz = get_hub_size(self.CONFIG['UPLOAD_DIR'])
                d_html = f'<div class="glass-box" style="display:flex;justify-content:space-around;padding:15px;margin-bottom:20px;text-align:center"><div>Space: <br><b>{format_size(tot)}</b></div><div style="color:#10b981">Free: <br><b>{format_size(fre)}</b></div><div style="color:var(--neon-orange)">Hub Size: <br><b>{format_size(sz)}</b></div></div>'
            except: 
                pass

        lns = load_json(LINKS_FILE)
        lks = load_json(LOCKS_FILE)
        ndl = load_json(NODL_FILE)
        
        lmap = {}
        for tk, d in lns.items():
            tgt = d.get('target') if isinstance(d, dict) else d
            if tgt not in lmap: lmap[tgt] = []
            lmap[tgt].append((tk, d))

        rows = f'<div class="file-item" data-name=".."><div class="file-info"><a href="/?dir={urllib.parse.quote("/".join(pts[:-1]))}" class="file-name" style="font-size:20px;">🔙 Return</a></div></div>' if pts else ""
        
        try: 
            ents = sorted(list(os.scandir(curr)), key=lambda e: (not e.is_dir(), e.name.lower()))
        except: 
            ents = []
        
        for e in ents:
            f = e.name
            if f in [CONFIG_FILE, LINKS_FILE, LOCKS_FILE, LOG_FILE, BLOCK_FILE, NODL_FILE, sys.argv[0].split('\\')[-1]]: continue
            
            is_d = e.is_dir()
            sz = format_size(e.stat().st_size) if not is_d else "--"
            dt = datetime.datetime.fromtimestamp(e.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            rel = self.get_rel(e.path)
            
            is_ndl = rel in ndl
            l_id = hashlib.md5(rel.encode()).hexdigest() if rel in lks else ""
            l_inf = f' <span style="color:orange;font-size:11px">[Pass: {lks[rel]}]</span>' if rel in lks and role == 'admin' else (' 🔒' if rel in lks else '')
            s_bdg = f'<span style="color:#3b82f6;font-size:10px;margin-left:8px;">👀 Stream Only</span>' if is_ndl else ""
            cb = f'<input type="checkbox" class="file-cb" value="{html.escape(f)}" onclick="toggleSelection(event)" style="margin-right:10px;accent-color:var(--accent);width:16px;height:16px;">' if role == 'admin' else ''
            
            if is_d:
                nx = f"{req_dir}/{f}".strip('/')
                ah = f'<button onclick="handleItemClick(\'/zip/{nx}\',\'download\',\'{l_id}\')">📦 ZIP</button><button onclick="lockItem(\'{f}\')">🔒 Lock</button><button onclick="renameItem(\'{f}\')">✏️ Rename</button><button onclick="copyItem(\'{f}\')">📄 Copy</button><button onclick="moveItem(\'{f}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f}\')">🗑️ Delete</button>' if role == 'admin' else f'<button onclick="handleItemClick(\'/zip/{nx}\',\'download\',\'{l_id}\')">📦 ZIP</button>'
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info">{cb}<span style="font-size:18px;">📁</span> <a href="/?dir={urllib.parse.quote(nx)}" class="file-name">{f}{l_inf}</a></div><div class="file-meta"><span>{dt}</span><span>{sz}</span></div><div class="actions"><button class="kebab-btn" onclick="toggleMenu(event, \'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{ah}</div></div></div>'
            else:
                ptype = get_preview_type(f)
                dl = urllib.parse.quote(f"/{req_dir}/{f}".replace('//', '/'))
                pcl = f"handleItemClick('/download{dl}', '{ptype or 'download'}', '{l_id}')"
                
                sh_bdg = ""
                if rel in lmap:
                    tk, d = lmap[rel][0]
                    ph = f" (Pass: {d.get('pwd')})" if isinstance(d, dict) and d.get('pwd') else ""
                    sh_bdg = f'<span style="color:var(--neon-red);font-size:10px;margin-left:8px;">● Shared{ph if role=="admin" else ""}</span>'
                    sh_btn = f'<button onclick="viewLink(\'{tk}\')">👁️ View Link</button><button onclick="renewItem(\'{f}\')">🔄 Renew</button><button class="action-red" onclick="unshareItem(\'{f}\')">🚫 Unshare</button>'
                else:
                    sh_btn = f'<button onclick="shareItem(\'{f}\')">🔗 Public Link</button><button onclick="limitedShareItem(\'{f}\')">⏳ Limited Link</button><button class="action-orange" onclick="pwdShareItem(\'{f}\')">🔑 Secure Link</button>'
                
                if role == 'admin':
                    ebtn = f'<button class="action-orange" onclick="editItem(\'{f}\',\'{l_id}\')">📝 Edit</button>' if f.split('.')[-1].lower() in ['txt','py','json','html','css','sh'] else ""
                    ah = f'<button onclick="toggleDl(\'{f}\')">{"✅ Enable DL" if is_ndl else "🚫 Disable DL"}</button>{sh_btn}{ebtn}<button onclick="lockItem(\'{f}\')">🔒 Lock</button><button onclick="renameItem(\'{f}\')">✏️ Rename</button><button onclick="copyItem(\'{f}\')">📄 Copy</button><button onclick="moveItem(\'{f}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f}\')">🗑️ Delete</button>'
                else: 
                    ah = ''
                
                dlb = f'<button onclick="handleItemClick(\'/download{dl}&dl=1\',\'download\',\'{l_id}\')" class="btn btn-action" style="padding:6px 12px;font-size:11px;">Download</button>' if role == 'admin' or not is_ndl else ''
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info">{cb}<span style="font-size:18px;">{get_icon(f, False)}</span> <span onclick="{pcl}" class="file-name">{f}{l_inf}{sh_bdg}{s_bdg}</span></div><div class="file-meta"><span>{dt}</span><span>{sz}</span></div><div class="actions">{dlb}<button class="kebab-btn" onclick="toggleMenu(event, \'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{ah}</div></div></div>'
        
        hout = UI_HTML.replace('{site_name}', self.CONFIG.get('SITE_NAME', 'HUB')) \
                      .replace('{role}', role.capitalize()) \
                      .replace('{breadcrumbs}', bc) \
                      .replace('{admin_top_btn}', sa_btn + a_btn) \
                      .replace('{admin_log_btn}', l_btn) \
                      .replace('{disk_dashboard}', d_html) \
                      .replace('{admin_upload_area}', up_a) \
                      .replace('{file_rows}', rows) \
                      .replace('{current_dir}', req_dir)
                      
        self._send_resp(hout)

    def _handle_upload(self, curr):
        try:
            content_type = self.headers.get('Content-Type')
            if not content_type or 'boundary=' not in content_type:
                self.send_error(400)
                return
                
            boundary = content_type.split('boundary=')[1].encode()
            remainbytes = int(self.headers.get('Content-Length', 0))
            
            # جستجو برای پیدا کردن اولین boundary
            while remainbytes > 0:
                line = self.rfile.readline()
                remainbytes -= len(line)
                if boundary in line:
                    break
                    
            while remainbytes > 0:
                filename = None
                
                # خواندن هدرهای فایل فعلی
                while remainbytes > 0:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if line == b'\r\n':
                        break
                    fn = re.findall(r'filename="(.*?)"', line.decode('utf-8', 'ignore'))
                    if fn:
                        filename = fn[0]
                        
                if not filename:
                    # اگر اسم فایلی پیدا نشد برو سراغ قسمت بعدی
                    while remainbytes > 0:
                        line = self.rfile.readline()
                        remainbytes -= len(line)
                        if boundary in line:
                            break
                    if b'--' + boundary + b'--' in line:
                        break
                    continue
                    
                # شروع نوشتن فایل
                out_path = os.path.join(curr, filename)
                with open(out_path, 'wb') as f:
                    preline = self.rfile.readline()
                    remainbytes -= len(preline)
                    while remainbytes > 0:
                        line = self.rfile.readline()
                        remainbytes -= len(line)
                        if boundary in line:
                            # رسیدن به انتهای فایل فعلی
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
                            
                add_log(self.client_address[0], f"Uploaded File: {filename}")
                
                # اگر این آخرین بخش بود، کلاً خارج شو
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
        if dl: 
            self.send_header("Content-Disposition", f'attachment; filename="{name or os.path.basename(p)}"')
        self.end_headers()
        with open(p, "rb") as f: 
            shutil.copyfileobj(f, self.wfile)
        
    def _send_resp(self, h):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(h.encode('utf-8'))

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
            
        FileHubHandler.CONFIG = cfg
        with socketserver.ThreadingTCPServer(("", int(cfg['PORT'])), FileHubHandler) as h:
            print(f"[*] Hub is running on port {cfg['PORT']}...")
            h.serve_forever()

if __name__ == "__main__": main()
