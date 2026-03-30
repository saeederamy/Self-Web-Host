import http.server, socketserver, os, urllib.parse, html, hashlib, sys, argparse, shutil, re, json, uuid, datetime, tempfile, time

CONFIG_FILE = "fileserver.conf"
LINKS_FILE = "public_links.json"
LOCKS_FILE = "folder_locks.json" 
LOG_FILE = "access_log.txt"
BLOCK_FILE = "ip_blocks.json"

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f: return json.load(f)
    return {}

def save_json(data, path):
    with open(path, 'w') as f: json.dump(data, f)

def add_log(ip, action):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = f"[{now}] IP: {ip} | Action: {action}\n"
    lines = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    lines.append(new_entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines[-100:])

def check_ip(ip):
    b = load_json(BLOCK_FILE)
    if ip in b and b[ip].get('block_until', 0) > time.time(): return True
    return False

def rec_fail(ip, max_fails):
    b = load_json(BLOCK_FILE); now = time.time()
    if ip not in b: b[ip] = {'fails': 1, 'last': now, 'block_until': 0}
    else:
        b[ip]['fails'] = 1 if now - b[ip]['last'] > 86400 else b[ip]['fails'] + 1
        b[ip]['last'] = now
    if b[ip]['fails'] >= max_fails: 
        b[ip]['block_until'] = now + 86400
        add_log(ip, "BANNED FOR 24 HOURS (Brute-Force)")
    save_json(b, BLOCK_FILE)

def clr_fail(ip):
    b = load_json(BLOCK_FILE)
    if ip in b: del b[ip]; save_json(b, BLOCK_FILE)

def load_config():
    if not os.path.exists(CONFIG_FILE): return None
    cfg = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                cfg[k] = v
    return cfg

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def is_in_locked_path(target_rel, l_path):
    if target_rel == l_path or target_rel.startswith(l_path + "/"): return True
    return False

COMMON_STYLE = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&display=swap');
    
    :root {{
        /* Default Theme: Black & White */
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
    }}

    [data-theme="black-blue"] {{
        --bg-dark: #0a0a0f; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #1a1a2e 0%, #0a0a0f 70%);
        --accent: #3b82f6;
        --accent-glow: rgba(59, 130, 246, 0.4);
        --accent-text: #ffffff;
    }}

    [data-theme="black-red"] {{
        --bg-dark: #0f0000; 
        --bg-gradient: radial-gradient(circle at 50% 0%, #2a0808 0%, #0f0000 70%);
        --accent: #ef4444;
        --accent-glow: rgba(239, 68, 68, 0.4);
        --accent-text: #ffffff;
    }}
    
    [data-theme="pure-black"] {{
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
    }}

    [data-theme="light"] {{
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
    }}
    
    body {{ 
        font-family: 'Inter', system-ui, sans-serif; 
        background: var(--bg-dark); 
        background-image: var(--bg-gradient);
        color: var(--text-main); 
        margin: 0; 
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
        transition: background 0.3s ease, color 0.3s ease;
    }}
    
    .glass-box {{ 
        background: var(--glass-bg); 
        backdrop-filter: blur(16px); 
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border); 
        border-radius: 16px; 
        box-shadow: var(--glass-shadow);
        transition: background 0.3s ease, border 0.3s ease, box-shadow 0.3s ease;
    }}
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-track {{ background: rgba(0,0,0,0.1); border-radius: 10px; }}
    ::-webkit-scrollbar-thumb {{ background: var(--glass-border); border-radius: 10px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--accent); }}
"""

UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{site_name}</title>
    <script>
        // Apply theme immediately to prevent flashing
        const savedTheme = localStorage.getItem('hub_theme') || 'black-white';
        document.documentElement.setAttribute('data-theme', savedTheme);
    </script>
    <style>
        """ + COMMON_STYLE + """
        .header {{ background: var(--glass-bg); backdrop-filter: blur(20px); border-bottom: 1px solid var(--glass-border); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 30px rgba(0,0,0,0.1); transition: all 0.3s ease; }}
        .logo {{ font-size: 22px; font-weight: 800; letter-spacing: 2px; color: var(--text-main); text-transform: uppercase; }}
        .header-controls {{ display: flex; align-items: center; gap: 15px; }}
        
        .badge {{ border: 1px solid var(--accent); padding: 4px 14px; border-radius: 50px; font-size: 11px; font-weight: 600; color: var(--accent); background: rgba(128, 128, 128, 0.1); box-shadow: 0 0 10px var(--accent-glow); text-transform: uppercase; white-space: nowrap; }}
        
        .theme-select {{ background: transparent; color: var(--text-main); border: 1px solid var(--glass-border); padding: 6px 10px; border-radius: 8px; font-size: 12px; font-family: 'Inter'; outline: none; cursor: pointer; max-width: 140px; }}
        .theme-select option {{ background: var(--bg-dark); color: var(--text-main); }}
        
        .logout-link {{ color: var(--neon-red); text-decoration: none; font-size: 13px; font-weight: 600; padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.3); transition: 0.3s; white-space: nowrap; }}
        .logout-link:hover {{ background: var(--neon-red); color: #fff; box-shadow: 0 0 15px var(--neon-red-glow); }}
        
        .container {{ max-width: 1200px; margin: 0 auto; padding: 30px 25px; transition: all 0.3s ease; box-sizing: border-box; }}
        
        .search-box {{ width: 100%; background: var(--input-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 16px 20px; color: var(--text-main); font-size: 15px; margin-bottom: 25px; box-sizing: border-box; transition: 0.3s; font-family: 'Inter'; }}
        .search-box:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }}
        
        .nav-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 15px; flex-wrap: wrap; }}
        .breadcrumbs {{ font-size: 14px; color: var(--text-muted); font-weight: 500; word-break: break-word; flex: 1; min-width: 200px; }}
        .breadcrumbs a {{ color: var(--text-main); text-decoration: none; transition: 0.2s; }}
        .breadcrumbs a:hover {{ color: var(--accent); text-shadow: 0 0 8px var(--accent-glow); }}
        
        .nav-buttons {{ display: flex; gap: 12px; flex-wrap: wrap; }}
        
        .file-list {{ }} 
        .file-item {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--glass-border); border-left: 2px solid transparent; transition: 0.2s; position: relative; gap: 10px; }}
        .file-item:first-child {{ border-top-left-radius: 16px; border-top-right-radius: 16px; }}
        .file-item:last-child {{ border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; border-bottom: none; }}
        .file-item:hover {{ background: var(--glass-border); border-left: 2px solid var(--accent); z-index: 50; }}
        
        .file-info {{ display: flex; align-items: center; gap: 15px; flex: 1; min-width: 0; }}
        .file-meta {{ display: flex; gap: 30px; font-size: 13px; color: var(--text-muted); justify-content: flex-end; padding-right: 15px; font-weight: 400; white-space: nowrap; }}
        .file-name {{ font-size: 15px; font-weight: 500; color: var(--text-main); text-decoration: none; word-break: break-word; overflow-wrap: anywhere; cursor: pointer; transition: 0.2s; display: inline-block; }}
        .file-name:hover {{ color: var(--accent); }}
        
        .actions {{ display: flex; align-items: center; gap: 12px; }}
        
        /* Glass Buttons */
        .btn {{ padding: 8px 16px; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; border: 1px solid var(--glass-border); background: var(--glass-bg); color: var(--text-main); transition: all 0.3s ease; display: inline-flex; align-items: center; justify-content: center; font-family: 'Inter'; backdrop-filter: blur(5px); white-space: nowrap; }}
        .btn:hover {{ background: var(--glass-border); transform: translateY(-2px); box-shadow: 0 5px 15px var(--glass-shadow); }}
        
        .btn-action {{ background: rgba(128, 128, 128, 0.1); color: var(--accent); border-color: var(--accent-glow); }}
        .btn-action:hover {{ background: var(--accent); color: var(--accent-text); box-shadow: 0 0 20px var(--accent-glow); }}
        
        .kebab-btn {{ background: transparent; border: 1px solid var(--glass-border); color: var(--text-main); cursor: pointer; font-size: 18px; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; transition: 0.3s; flex-shrink: 0; }}
        .kebab-btn:hover {{ background: var(--glass-border); }}
        
        /* Dropdown Menu */
        .dropdown-content {{ display: none; position: absolute; right: 24px; top: 55px; background: var(--bg-dark); backdrop-filter: blur(20px); border: 1px solid var(--glass-border); min-width: 200px; border-radius: 12px; z-index: 100; box-shadow: var(--glass-shadow); overflow: hidden; padding: 8px; }}
        .dropdown-content button {{ width: 100%; padding: 12px 16px; text-align: left; background: transparent; border: none; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; display: block; border-radius: 8px; transition: 0.2s; font-family: 'Inter'; margin-bottom: 2px; }}
        .dropdown-content button:hover {{ background: var(--glass-border); color: var(--text-main); padding-left: 20px; }}
        .dropdown-content button.action-red:hover {{ background: rgba(239, 68, 68, 0.15); color: var(--neon-red); border-left: 2px solid var(--neon-red); }}
        .dropdown-content button.action-orange:hover {{ background: rgba(249, 115, 22, 0.15); color: var(--neon-orange); border-left: 2px solid var(--neon-orange); }}
        .dropdown-content button.action-accent:hover {{ background: rgba(128, 128, 128, 0.15); color: var(--accent); border-left: 2px solid var(--accent); }}
        
        .show {{ display: block; animation: fadeIn 0.2s ease; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        
        /* Modals */
        .modal {{ display: none; position: fixed; z-index: 2000; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(15px); justify-content: center; align-items: center; }}
        .modal-content {{ width: 90%; height: 85%; max-width: 1000px; position: relative; display: flex; justify-content: center; align-items: center; animation: scaleIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }}
        @keyframes scaleIn {{ from {{ transform: scale(0.9); opacity: 0; }} to {{ transform: scale(1); opacity: 1; }} }}
        .modal-close {{ position: absolute; top: -40px; right: 0; color: #fff; font-size: 35px; cursor: pointer; opacity: 0.6; transition: 0.3s; line-height: 1; }}
        .modal-close:hover {{ opacity: 1; color: var(--neon-red); text-shadow: 0 0 15px var(--neon-red-glow); }}
        
        .tree-item {{ padding: 12px 15px; cursor: pointer; border-radius: 8px; transition: 0.2s; color: var(--text-muted); font-size: 14px; margin-bottom: 4px; display:flex; align-items:center; border: 1px solid transparent; word-break: break-all; }}
        .tree-item:hover {{ background: var(--glass-border); color: var(--text-main); }}
        .tree-item.selected {{ background: rgba(128, 128, 128, 0.15); color: var(--accent); font-weight: 600; border: 1px solid var(--accent-glow); box-shadow: 0 0 15px var(--accent-glow); }}
        
        iframe, video, img {{ border-radius: 12px; border: 1px solid var(--glass-border); max-width: 100%; max-height: 100%; background: rgba(0,0,0,0.5); box-shadow: var(--glass-shadow); }}
        
        /* --- Mobile Responsiveness --- */
        @media (max-width: 768px) {{
            .header {{ flex-direction: column; padding: 15px; gap: 15px; }}
            .header-controls {{ width: 100%; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
            .container {{ padding: 15px 12px; }}
            .file-meta {{ display: none; }} /* Hide dates and sizes on small screens */
            .file-item {{ padding: 12px 15px; flex-wrap: wrap; }}
            .actions {{ width: auto; justify-content: flex-end; }}
            .file-info {{ width: 100%; margin-bottom: 5px; }}
            .dropdown-content {{ right: 15px; top: 50px; }}
            .nav-row {{ flex-direction: column; align-items: stretch; }}
            .nav-buttons {{ justify-content: flex-start; }}
            .btn {{ padding: 8px 12px; font-size: 12px; }}
            .search-box {{ padding: 12px 15px; margin-bottom: 15px; }}
            .modal-content {{ width: 95%; height: 90%; }}
        }}
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
                <a href="/logout" class="logout-link">Logout</a>
            </div>
        </div>
    </div>
    <div class="container">
        <input type="text" id="search" class="search-box glass-box" placeholder="🔍 Search files..." onkeyup="doSearch()">
        <div class="nav-row">
            <div class="breadcrumbs">{breadcrumbs}</div>
            <div class="nav-buttons">
                {admin_log_btn}
                {admin_top_btn}
            </div>
        </div>
        {admin_upload_area}
        <div class="file-list glass-box" id="list">{file_rows}</div>
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
            <textarea readonly id="log-viewer" style="width:100%; height:100%; background:rgba(0,0,0,0.8); color:#10b981; border:1px solid var(--glass-border); padding:20px; font-family:monospace; font-size:13px; resize:none; border-radius:12px; outline:none; box-sizing:border-box;">{log_data}</textarea>
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
        
        // Setup Theme
        const themeSelector = document.getElementById('themeSelector');
        if(themeSelector) themeSelector.value = savedTheme;
        
        function changeTheme(theme) {{
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('hub_theme', theme);
        }}
        
        function handleItemClick(url, type, lockId) {{
            if (lockId) {{
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 This item is Locked. Please enter password:");
                if (p) {{ document.cookie = "lock_" + lockId + "=" + p + ";path=/"; }} 
                else {{ return; }}
            }}
            if (type === 'download') {{ window.location.href = url; }} 
            else {{ openPreview(url, type); }}
        }}

        function doSearch() {{
            let q = document.getElementById('search').value.toLowerCase();
            document.querySelectorAll('.file-item').forEach(item => {{
                let name = item.getAttribute('data-name').toLowerCase();
                item.style.display = (name.includes(q) || name === '..') ? 'flex' : 'none';
            }});
        }}
        
        function toggleMenu(event, id) {{ 
            event.stopPropagation();
            document.querySelectorAll('.dropdown-content').forEach(d => {{ if(d.id !== id) d.classList.remove('show'); }}); 
            document.getElementById(id).classList.toggle('show'); 
        }}
        
        window.onclick = (e) => {{ 
            if (!e.target.closest('.dropdown-content') && !e.target.matches('.kebab-btn')) {{
                document.querySelectorAll('.dropdown-content').forEach(d => d.classList.remove('show')); 
            }}
        }}
        
        function openPreview(url, type) {{
            const body = document.getElementById('previewBody'); body.innerHTML = ''; document.getElementById('previewModal').style.display = 'flex';
            if (type === 'image') body.innerHTML = `<img src="${{url}}">`;
            else if (type === 'video') body.innerHTML = `<video controls autoplay style="width:100%;"><source src="${{url}}"></video>`;
            else if (type === 'audio') body.innerHTML = `<audio controls autoplay style="width:300px;"><source src="${{url}}"></audio>`;
            else if (type === 'pdf') body.innerHTML = `<iframe src="${{url}}" style="width:100%; height:100%; background:#fff;"></iframe>`;
            else window.location.href = url;
        }}
        function closePreview() {{ document.getElementById('previewModal').style.display = 'none'; document.getElementById('previewBody').innerHTML = ''; }}
        
        let treeAction = ''; let treeTarget = ''; let treeSelected = null;
        function openTreeModal(act, tgt) {{
            treeAction = act; treeTarget = tgt; treeSelected = null;
            let icon = act === 'move' ? '✂️ Move ' : '📄 Copy ';
            document.getElementById('tree-title').innerText = icon + tgt + " to...";
            document.getElementById('treeModal').style.display = 'flex';
            document.getElementById('tree-list').innerHTML = '<div style="color:var(--accent);text-align:center;padding:30px;font-weight:600;">Scanning Directories...</div>';
            
            fetch('/action', {{method:'POST', body:new URLSearchParams({{action:'get_tree'}})}}).then(r=>r.json()).then(dirs => {{
                let h = '';
                dirs.forEach(d => {{
                    let pad = d === '/' ? 0 : (d.split('/').length - 1) * 20;
                    let name = d === '/' ? 'Root Directory ( / )' : d.split('/').pop();
                    let folIcon = d === '/' ? '🖧' : '📁';
                    h += `<div class="tree-item" style="padding-left:${{pad + 15}}px" onclick="selectTreeItem(this, '${{d}}')">${{folIcon}} &nbsp; ${{name}}</div>`;
                }});
                document.getElementById('tree-list').innerHTML = h;
            }});
        }}
        function selectTreeItem(el, path) {{
            document.querySelectorAll('.tree-item').forEach(i => i.classList.remove('selected'));
            el.classList.add('selected');
            treeSelected = path === '/' ? '' : path.substring(1);
        }}
        function confirmTreeAction() {{
            if(treeSelected === null) return alert('Please select a destination folder first.');
            fetch('/action', {{method:'POST', body:new URLSearchParams({{action:treeAction, target:treeTarget, dir:currentDir, dest:treeSelected}})}}).then(()=>location.reload());
        }}

        function clearLogs() {{ if(confirm('Clear all system logs?')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'clear_logs'}}) }}).then(()=>location.reload()); }}
        function createFolder() {{ let n = prompt("New Folder Name:"); if(n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'mkdir', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function createFile() {{ let n = prompt("New File Name (e.g. script.py):"); if(n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'mkfile', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function deleteItem(n) {{ if(confirm('Permanently delete ' + n + '?')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'delete', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function renameItem(n) {{ let nn = prompt("Rename " + n + " to:", n); if(nn && nn !== n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'rename', target:n, new_name:nn, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function moveItem(n) {{ openTreeModal('move', n); }}
        function copyItem(n) {{ openTreeModal('copy', n); }}
        function lockItem(n) {{ let pwd = prompt("Set Lock Password (leave empty to remove lock):"); if(pwd !== null) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'lock_item', target:n, dir:currentDir, pwd:pwd}}) }}).then(()=>location.reload()); }}
        
        function shareItem(n) {{ fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share', target:n, dir:currentDir}}) }}).then(r=>r.text()).then(l=>{{ prompt("Public Link created:", window.location.origin+l); location.reload(); }}); }}
        function limitedShareItem(n) {{ let limit = prompt("Max Downloads:", "1"); if(limit && parseInt(limit)>0) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share_limit', target:n, dir:currentDir, limit:parseInt(limit)}}) }}).then(r=>r.text()).then(l=>{{ prompt("Limited Link created:", window.location.origin+l); location.reload(); }}); }}
        function pwdShareItem(n) {{ let pwd = prompt("Set Link Password:"); if(pwd) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share_pwd', target:n, dir:currentDir, pwd:pwd}}) }}).then(r=>r.text()).then(l=>{{ prompt("Secure Link created:", window.location.origin+l); location.reload(); }}); }}
        function renewItem(n) {{ if(confirm('Generate a new link for ' + n + '? (Old link will expire)')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'renew', target:n, dir:currentDir}}) }}).then(r=>r.text()).then(l=>{{ prompt("New Link:", window.location.origin+l); location.reload(); }}); }}
        function unshareItem(n) {{ fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'unshare', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function viewLink(tk) {{ prompt("Current Shared Link:", window.location.origin + "/p/" + tk); }}

        function editItem(n, lockId) {{
            if (lockId) {{
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 Locked File. Enter password to edit:");
                if (p) document.cookie = "lock_" + lockId + "=" + p + ";path=/";
                else return;
            }}
            fetch('/download/' + currentDir + '/' + n).then(r => r.text()).then(t => {{
                document.getElementById('edit-name').innerText = "📝 Editing: " + n;
                document.getElementById('edit-box').value = t;
                document.getElementById('edit-box').setAttribute('data-target', n);
                document.getElementById('editModal').style.display = 'flex';
            }});
        }}
        function saveEdit() {{
            let n = document.getElementById('edit-box').getAttribute('data-target');
            let t = document.getElementById('edit-box').value;
            fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'save_text', target:n, dir:currentDir, content:t}}) }}).then(()=>{{ document.getElementById('editModal').style.display='none'; location.reload(); }});
        }}

        const dropZone = document.getElementById('drop-zone');
        if(dropZone) {{
            const input = document.getElementById('file-input'); dropZone.onclick = () => input.click();
            
            dropZone.addEventListener('dragover', (e) => {{ e.preventDefault(); dropZone.style.borderColor = "var(--accent)"; dropZone.style.background = "rgba(128,128,128,0.1)"; }});
            dropZone.addEventListener('dragleave', (e) => {{ e.preventDefault(); dropZone.style.borderColor = "var(--glass-border)"; dropZone.style.background = "var(--glass-bg)"; }});
            dropZone.addEventListener('drop', (e) => {{ e.preventDefault(); dropZone.style.borderColor = "var(--glass-border)"; dropZone.style.background = "var(--glass-bg)"; input.files = e.dataTransfer.files; input.dispatchEvent(new Event('change')); }});

            input.onchange = (e) => {{
                if(e.target.files.length === 0) return;
                const fd = new FormData(); for(let f of e.target.files) fd.append('file', f);
                document.getElementById('progress-wrapper').style.display = 'block';
                const xhr = new XMLHttpRequest(); xhr.open('POST', '/upload?dir='+encodeURIComponent(currentDir), true);
                xhr.upload.onprogress = (ev) => {{ 
                    let percent = Math.round((ev.loaded/ev.total)*100);
                    document.getElementById('progress-bar').style.width = percent + '%'; 
                    document.getElementById('progress-bar').style.boxShadow = "0 0 15px var(--accent)";
                }};
                xhr.onload = () => location.reload(); xhr.send(fd);
            }};
        }}
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&display=swap');
        
        body {{ 
            display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; margin: 0;
            background: linear-gradient(45deg, #000000, #171717, #262626, #000000);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            font-family: 'Inter', system-ui, sans-serif; 
        }}
        @keyframes gradientBG {{ 0% {{background-position: 0% 50%;}} 50% {{background-position: 100% 50%;}} 100% {{background-position: 0% 50%;}} }}
        
        .login-card {{ 
            padding: 40px; width: 90%; max-width: 340px; text-align: center; 
            background: rgba(20, 20, 20, 0.6);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.9);
            border-radius: 20px;
            position: relative; overflow: hidden;
            box-sizing: border-box;
        }}
        
        .login-card::before {{
            content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 60%);
            z-index: -1; animation: pulse 6s ease-in-out infinite alternate;
        }}
        @keyframes pulse {{ 0% {{transform: scale(0.8);}} 100% {{transform: scale(1.2);}} }}

        h2 {{ color: #fff; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 30px; text-shadow: 0 0 20px rgba(255,255,255,0.2); word-break: break-word; }}
        
        input {{ 
            width: 100%; padding: 16px; margin: 0 0 25px 0; 
            background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.2); 
            color: white; border-radius: 12px; box-sizing: border-box; outline: none; 
            font-size: 15px; text-align: center; letter-spacing: 4px; transition: 0.3s;
            font-family: 'Inter';
        }}
        input:focus {{ border-color: #fff; box-shadow: 0 0 20px rgba(255,255,255,0.2); background: rgba(0,0,0,0.8); }}
        input::placeholder {{ letter-spacing: 2px; color: rgba(255,255,255,0.3); }}
        
        button {{ 
            width: 100%; padding: 16px; 
            background: #ffffff; color: #000000; 
            border: none; border-radius: 12px; cursor: pointer; 
            font-weight: 800; font-size: 15px; text-transform: uppercase; letter-spacing: 1px;
            box-shadow: 0 0 20px rgba(255,255,255,0.2); transition: 0.3s;
            font-family: 'Inter';
        }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 0 30px rgba(255, 255, 255, 0.4); background: #e5e5e5; }}
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
    def get_role(self):
        ck = self.headers.get("Cookie", "")
        if f"auth={hashlib.sha256(self.CONFIG['ADMIN_PWD'].encode()).hexdigest()}" in ck: return "admin"
        if f"auth={hashlib.sha256(self.CONFIG['GUEST_PWD'].encode()).hexdigest()}" in ck: return "user"
        return None

    def get_safe_path(self, req_dir):
        base = os.path.abspath(self.CONFIG['UPLOAD_DIR'])
        t = os.path.abspath(os.path.join(base, req_dir.strip('/')))
        return t if t.startswith(base) else base

    def get_rel(self, p):
        r = os.path.relpath(p, os.path.abspath(self.CONFIG['UPLOAD_DIR'])).replace('\\', '/')
        return "" if r == "." else r

    def do_GET(self):
        if check_ip(self.client_address[0]):
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
                    add_log(self.client_address[0], f"Public Link Download: {target_rel}")
                    if limit > 0:
                        lns[tk]['limit'] -= 1
                        if lns[tk]['limit'] <= 0: del lns[tk]
                        save_json(lns, LINKS_FILE)
                    return self._send_file(target, dl=True)
            return self.send_error(404)
        
        role = self.get_role()
        if not role: self._send_resp(LOGIN_HTML.format(site_name=self.CONFIG['SITE_NAME'])); return
        
        q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]; curr = self.get_safe_path(q)
        rel_curr = self.get_rel(curr)
        
        if parsed.path.startswith("/zip/"):
            target = self.get_safe_path(urllib.parse.unquote(parsed.path[5:]))
            if not self.check_item_lock(self.get_rel(target)): return
            if os.path.isdir(target):
                add_log(self.client_address[0], f"Downloaded ZIP: {self.get_rel(target)}")
                tmp_base = tempfile.mktemp(); shutil.make_archive(tmp_base, 'zip', target); zip_path = tmp_base + '.zip'
                self._send_file(zip_path, dl=True, name=os.path.basename(target)+".zip"); os.remove(zip_path)
            return
        if parsed.path == "/": 
            if self.check_item_lock(rel_curr): self._serve_ui(role, curr, q)
        elif parsed.path.startswith("/download/"):
            target = self.get_safe_path(urllib.parse.unquote(parsed.path[10:]))
            if not self.check_item_lock(self.get_rel(target)): return
            if os.path.isfile(target): 
                add_log(self.client_address[0], f"Downloaded File: {self.get_rel(target)}")
                self._send_file(target, dl=True)
        elif parsed.path == "/logout":
            add_log(self.client_address[0], "Logged Out")
            self.send_response(302); self.send_header("Set-Cookie", "auth=; Max-Age=0; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers()

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

    def do_POST(self):
        if check_ip(self.client_address[0]): self.send_error(403); return
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/login":
            l = int(self.headers.get('Content-Length', 0)); pwd = urllib.parse.parse_qs(self.rfile.read(l).decode()).get('password', [''])[0]
            if pwd == self.CONFIG['ADMIN_PWD'] or pwd == self.CONFIG['GUEST_PWD']:
                clr_fail(self.client_address[0])
                add_log(self.client_address[0], "Login Successful")
                tk = hashlib.sha256(pwd.encode()).hexdigest(); self.send_response(302); self.send_header("Set-Cookie", f"auth={tk}; Path=/; HttpOnly"); self.send_header("Location", "/"); self.end_headers()
            else: 
                max_fails = int(self.CONFIG.get('MAX_FAILS', 15))
                rec_fail(self.client_address[0], max_fails)
                self.send_error(401)
                return
                
        if self.get_role() != "admin": return
        q = urllib.parse.parse_qs(parsed.query).get('dir', [''])[0]; curr = self.get_safe_path(q)
        
        if parsed.path == "/upload": self._handle_upload(curr)
        elif parsed.path == "/action":
            l = int(self.headers.get('Content-Length', 0)); data = urllib.parse.parse_qs(self.rfile.read(l).decode())
            act, target = data.get('action',[''])[0], data.get('target',[''])[0]
            
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
                open(LOG_FILE, 'w').close(); add_log(self.client_address[0], "Logs cleared"); self.send_response(200); self.end_headers(); return
            
            tp = os.path.join(curr, target); rel = self.get_rel(tp)
            if act == 'mkdir': os.makedirs(tp, exist_ok=True)
            elif act == 'mkfile': 
                if not os.path.exists(tp): open(tp, 'w', encoding='utf-8').close()
            elif act == 'delete' and os.path.exists(tp): shutil.rmtree(tp) if os.path.isdir(tp) else os.remove(tp)
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
            elif act in ['share', 'share_limit', 'share_pwd', 'renew'] and os.path.isfile(tp):
                lns = load_json(LINKS_FILE)
                if act == 'renew': lns = {k:v for k,v in lns.items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                tk = str(uuid.uuid4())[:8]; limit = int(data.get('limit', ['-1'])[0]) if act == 'share_limit' else -1
                lns[tk] = {'target': rel, 'limit': limit, 'pwd': data.get('pwd', [''])[0] if act == 'share_pwd' else ""}
                save_json(lns, LINKS_FILE); self.send_response(200); self.end_headers(); self.wfile.write(f"/p/{tk}".encode()); return
            elif act == 'unshare':
                lns = load_json(LINKS_FILE)
                lns = {k:v for k,v in lns.items() if (v.get('target') if isinstance(v, dict) else v) != rel}
                save_json(lns, LINKS_FILE)
            self.send_response(200); self.end_headers()

    def _serve_ui(self, role, curr, req_dir):
        pts = [p for p in req_dir.split('/') if p]; bc = f'<a href="/">Root</a>'; acc = ""
        for p in pts: acc += f"/{p}"; bc += f' <span style="opacity:0.3">/</span> <a href="/?dir={urllib.parse.quote(acc)}">{p}</a>'
        admin_btn = '<button class="btn btn-action" onclick="createFolder()">+ New Folder</button><button class="btn btn-action" onclick="createFile()">+ New File</button>' if role == 'admin' else ''
        admin_log_btn = '<button class="btn" style="background:rgba(16, 185, 129, 0.15); color:var(--neon-green); border-color:rgba(16, 185, 129, 0.4);" onclick="document.getElementById(\'logModal\').style.display=\'flex\'">📜 System Logs</button>' if role == 'admin' else ''
        up_area = '<div class="glass-box" id="drop-zone" style="padding:25px; text-align:center; margin-bottom:25px; cursor:pointer; border: 2px dashed var(--glass-border); transition: 0.3s;"><p style="font-size:14px; font-weight:500; color:var(--text-muted); margin:0;">☁️ Drag & Drop files here or click to upload</p><input type="file" id="file-input" hidden multiple><div id="progress-wrapper" style="display:none; height:4px; background:rgba(0,0,0,0.5); margin-top:15px; border-radius:10px; overflow:hidden;"><div id="progress-bar" style="width:0; height:100%; background:var(--accent); transition:width 0.2s;"></div></div></div>' if role == 'admin' else ''
        lns = load_json(LINKS_FILE); locks = load_json(LOCKS_FILE); log_content = ""
        if role == 'admin' and os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f: log_content = "".join(f.readlines())
        rows = ""
        if pts: rows += f'<div class="file-item" data-name=".."><div class="file-info"><span style="font-size:20px">🔙</span><a href="/?dir={urllib.parse.quote("/".join(pts[:-1]))}" class="file-name" style="color:var(--accent);">Return to Parent</a></div></div>'
        try: files = sorted(os.listdir(curr))
        except: files = []
        
        for f in files:
            if f in [CONFIG_FILE, LINKS_FILE, LOCKS_FILE, LOG_FILE, BLOCK_FILE]: continue
            full = os.path.join(curr, f); rel = self.get_rel(full); is_d = os.path.isdir(full); stat = os.stat(full)
            size = format_size(stat.st_size) if not is_d else "--"; date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            
            lock_id = hashlib.md5(rel.encode()).hexdigest() if rel in locks else ""
            lock_info = f' <span style="color:var(--neon-orange); font-size:11px; margin-left:8px; text-shadow:0 0 8px var(--neon-orange-glow); white-space:nowrap;">[Pass: {locks[rel]}]</span>' if rel in locks and role == 'admin' else (' 🔒' if rel in locks else '')
            
            if is_d:
                nx = f"{req_dir}/{f}".strip('/')
                dl_zip_click = f"handleItemClick('/zip/{nx}', 'download', '{lock_id}')"
                admin_h = f'<button class="action-accent" onclick="{dl_zip_click}">📦 Download ZIP</button><button class="action-orange" onclick="lockItem(\'{f}\')">🔒 Lock / Unlock</button><button class="action-orange" onclick="renameItem(\'{f}\')">✏️ Rename</button><button class="action-accent" onclick="copyItem(\'{f}\')">📄 Copy</button><button class="action-accent" onclick="moveItem(\'{f}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f}\')">🗑️ Delete</button>' if role == 'admin' else f'<button class="action-accent" onclick="{dl_zip_click}">📦 Download ZIP</button>'
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info"><span style="font-size:18px; flex-shrink:0;">📁</span><a href="/?dir={urllib.parse.quote(nx)}" class="file-name">{f}{lock_info}</a></div><div class="file-meta"><span>{date}</span><span style="width:60px; text-align:right;">{size}</span></div><div class="actions"><button class="kebab-btn" onclick="toggleMenu(event, \'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{admin_h}</div></div></div>'
            else:
                p_type = get_preview_type(f); dl = urllib.parse.quote(f"/{req_dir}/{f}".replace('//', '/'))
                p_type_str = p_type if p_type else 'download'
                p_click = f"handleItemClick('/download{dl}', '{p_type_str}', '{lock_id}')"
                
                share_badge = ""
                view_link_btn = ""
                for tk, data in lns.items():
                    if (data.get('target') if isinstance(data, dict) else data) == rel:
                        pwd_hint = f" (Pass: {data.get('pwd')})" if isinstance(data, dict) and data.get('pwd') else ""
                        share_badge = f'<span style="color:var(--neon-red); font-size:10px; margin-left:8px; text-shadow:0 0 8px var(--neon-red-glow); white-space:nowrap;">● Shared{pwd_hint if role == "admin" else ""}</span>'
                        view_link_btn = f'<button class="action-accent" onclick="viewLink(\'{tk}\')">👁️ View Link</button>'
                        break
                        
                is_text = f.split('.')[-1].lower() in ['txt', 'md', 'py', 'json', 'html', 'css', 'js', 'conf', 'sh']
                
                if role == 'admin':
                    s_btns = f'{view_link_btn}<button class="action-accent" onclick="renewItem(\'{f}\')">🔄 Renew Link</button><button class="action-red" onclick="unshareItem(\'{f}\')">🚫 Unshare</button>' if share_badge else f'<button class="action-accent" onclick="shareItem(\'{f}\')">🔗 Public Link</button><button class="action-accent" onclick="limitedShareItem(\'{f}\')">⏳ Limited Link</button><button class="action-orange" onclick="pwdShareItem(\'{f}\')">🔑 Secure Link</button>'
                    edit_btn = f'<button class="action-orange" onclick="editItem(\'{f}\', \'{lock_id}\')">📝 Edit File</button>' if is_text else ""
                    admin_h = f'{s_btns}{edit_btn}<button class="action-orange" onclick="lockItem(\'{f}\')">🔒 Lock / Unlock</button><button class="action-orange" onclick="renameItem(\'{f}\')">✏️ Rename</button><button class="action-accent" onclick="copyItem(\'{f}\')">📄 Copy</button><button class="action-accent" onclick="moveItem(\'{f}\')">✂️ Move</button><button class="action-red" onclick="deleteItem(\'{f}\')">🗑️ Delete</button>'
                else: 
                    admin_h = ''
                    
                dl_btn = f'<button onclick="handleItemClick(\'/download{dl}\', \'download\', \'{lock_id}\')" class="btn btn-action" style="padding: 6px 12px; font-size: 11px;">Download</button>'
                
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info"><span style="font-size:18px; flex-shrink:0;">{get_icon(f, False)}</span><span onclick="{p_click}" class="file-name">{f}{lock_info}{share_badge}</span></div><div class="file-meta"><span>{date}</span><span style="width:60px; text-align:right;">{size}</span></div><div class="actions">{dl_btn}<button class="kebab-btn" onclick="toggleMenu(event, \'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{admin_h}</div></div></div>'
        
        self._send_resp(UI_HTML.format(site_name=self.CONFIG['SITE_NAME'], role=role.capitalize(), breadcrumbs=bc, admin_top_btn=admin_btn, admin_log_btn=admin_log_btn, admin_upload_area=up_area, file_rows=rows, current_dir=req_dir, log_data=log_content))

    def _handle_upload(self, curr):
        try:
            ct = self.headers.get('Content-Type'); bnd = re.findall(r'boundary=(.*)', ct)[0].encode()
            rem = int(self.headers.get('Content-Length')); line = self.rfile.readline(); rem -= len(line)
            while rem > 0:
                line = self.rfile.readline(); rem -= len(line); fn = re.findall(r'filename="(.*)"', line.decode())
                if fn:
                    add_log(self.client_address[0], f"Uploaded File: {fn[0]}")
                    self.rfile.readline(); self.rfile.readline(); out = os.path.join(curr, fn[0])
                    with open(out, 'wb') as f:
                        pre = self.rfile.readline(); rem -= len(pre)
                        while rem > 0:
                            line = self.rfile.readline(); rem -= len(line)
                            if bnd in line: f.write(pre[:-2]); break
                            else: f.write(pre); pre = line
                    self.send_response(200); self.end_headers(); return
            self.send_error(400)
        except: self.send_error(500)
        
    def _send_file(self, p, dl=False, name=None):
        self.send_response(200); self.send_header("Content-Type", "application/octet-stream")
        if dl: self.send_header("Content-Disposition", f'attachment; filename="{name or os.path.basename(p)}"')
        self.end_headers()
        with open(p, "rb") as f: shutil.copyfileobj(f, self.wfile)
        
    def _send_resp(self, h):
        self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(h.encode('utf-8'))

def main():
    p = argparse.ArgumentParser(); p.add_argument('cmd', choices=['setup', 'run']); args = p.parse_args()
    if args.cmd == "setup":
        print("\n--- HUB SETUP (Press Enter for Defaults) ---")
        sn = input("Site Name [BLACK HUB]: ") or "BLACK HUB"
        ap = input("Admin Password [admin]: ") or "admin"
        gp = input("Guest Password [1234]: ") or "1234"
        pt = input("Port [5000]: ") or "5000"
        sd = input("Storage Path [./uploads]: ") or "./uploads"
        mf = input("Max Failed Logins before Ban [15]: ") or "15"
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: 
            f.write(f"SITE_NAME={sn}\nADMIN_PWD={ap}\nGUEST_PWD={gp}\nPORT={pt}\nUPLOAD_DIR={sd}\nMAX_FAILS={mf}\n")
        if not os.path.exists(sd): os.makedirs(sd)
        print(f"\n[✔] Setup Complete! Run 'python your_file.py run' to start.")
    elif args.cmd == "run":
        cfg = load_config()
        if not cfg: return print("[!] Run setup first.")
        FileHubHandler.CONFIG = cfg
        with socketserver.ThreadingTCPServer(("", int(cfg['PORT'])), FileHubHandler) as h:
            print(f"[*] Hub live at port {cfg['PORT']}"); h.serve_forever()

if __name__ == "__main__": main()
