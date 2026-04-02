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

def rec_fail(ip):
    b = load_json(BLOCK_FILE); now = time.time()
    if ip not in b: b[ip] = {'fails': 1, 'last': now, 'block_until': 0}
    else:
        b[ip]['fails'] = 1 if now - b[ip]['last'] > 86400 else b[ip]['fails'] + 1
        b[ip]['last'] = now
    if b[ip]['fails'] >= 15: 
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
    :root {{ 
        --bg: #000000; --card: rgba(20, 20, 20, 0.7); --border: rgba(255, 255, 255, 0.08);
        --accent-red: #ff3131; --text: #e0e0e0; --subtext: #888;
        --glass: blur(15px);
    }}
    body {{ 
        font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; min-height: 100vh;
        background-image: radial-gradient(circle at center, #111 0%, #000 100%);
    }}
    .glass-box {{ background: var(--card); backdrop-filter: var(--glass); border: 1px solid var(--border); border-radius: 16px; }}
    .tree-item {{ padding: 10px 15px; cursor: pointer; border-radius: 6px; transition: 0.2s; color: var(--text); font-size: 14px; margin-bottom: 2px; display:flex; align-items:center; }}
    .tree-item:hover {{ background: rgba(255,255,255,0.08); }}
    .tree-item.selected {{ background: rgba(255,255,255,0.15); color: #fff; font-weight: bold; border: 1px solid var(--border); }}
"""

UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{site_name}</title>
    <style>
        """ + COMMON_STYLE + """
        .header {{ background: rgba(0,0,0,0.8); backdrop-filter: var(--glass); border-bottom: 1px solid var(--border); padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; }}
        .logo {{ font-size: 20px; font-weight: 800; letter-spacing: 1px; color: #fff; text-transform: uppercase; }}
        .badge {{ border: 1px solid var(--accent-red); padding: 2px 12px; border-radius: 50px; font-size: 11px; color: var(--accent-red); background: rgba(255,49,49,0.1); }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 25px; }}
        .search-box {{ width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 12px; padding: 14px 20px; color: white; font-size: 14px; margin-bottom: 20px; box-sizing: border-box; transition: 0.3s; }}
        .search-box:focus {{ outline: none; border-color: #555; background: rgba(255,255,255,0.08); }}
        .nav-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
        .breadcrumbs {{ font-size: 13px; color: var(--subtext); }}
        .breadcrumbs a {{ color: #ccc; text-decoration: none; }}
        .file-item {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--border); transition: 0.2s; position: relative; }}
        .file-item:hover {{ background: rgba(255,255,255,0.03); }}
        .file-info {{ display: flex; align-items: center; gap: 15px; flex: 2; min-width: 0; }}
        .file-meta {{ flex: 1; display: flex; gap: 20px; font-size: 12px; color: var(--subtext); justify-content: flex-end; margin-right: 20px; }}
        .file-name {{ font-size: 14px; color: var(--text); text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }}
        .file-name:hover {{ color: #fff; }}
        .btn {{ padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; text-decoration: none; border: 1px solid var(--border); background: rgba(255,255,255,0.05); color: #fff; transition: 0.2s; }}
        .btn-action {{ background: #fff; color: #000; border: none; }}
        .kebab-btn {{ background: none; border: none; color: var(--subtext); cursor: pointer; font-size: 18px; padding: 5px 10px; border-radius: 50%; }}
        .dropdown-content {{ display: none; position: absolute; right: 20px; top: 40px; background: #111; border: 1px solid var(--border); min-width: 170px; border-radius: 10px; z-index: 100; box-shadow: 0 10px 30px rgba(0,0,0,0.8); overflow: hidden; }}
        .dropdown-content button {{ width: 100%; padding: 10px 15px; text-align: left; background: none; border: none; color: #ccc; font-size: 13px; cursor: pointer; display: block; }}
        .dropdown-content button:hover {{ background: #222; color: #fff; }}
        .btn-del-text {{ color: var(--accent-red) !important; }}
        .show {{ display: block; }}
        .modal {{ display: none; position: fixed; z-index: 2000; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); backdrop-filter: blur(10px); justify-content: center; align-items: center; }}
        .modal-content {{ width: 90%; height: 85%; position: relative; display: flex; justify-content: center; align-items: center; }}
        .modal-close {{ position: absolute; top: -45px; right: 0; color: #fff; font-size: 35px; cursor: pointer; }}
        iframe, video, img {{ border-radius: 8px; border: 1px solid var(--border); max-width: 100%; max-height: 100%; background: #000; }}
        @media (max-width: 768px) {{ .file-meta {{ display: none; }} }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">{site_name}</div>
        <div style="display:flex; align-items:center; gap:15px;">
            <span class="badge">{role}</span>
            <a href="/logout" style="color: var(--subtext); text-decoration: none; font-size: 12px;">Logout</a>
        </div>
    </div>
    <div class="container">
        <input type="text" id="search" class="search-box" placeholder="Search files..." onkeyup="doSearch()">
        <div class="nav-row">
            <div class="breadcrumbs">{breadcrumbs}</div>
            <div style="display:flex; gap:10px;">
                {admin_log_btn}
                {admin_top_btn}
            </div>
        </div>
        {admin_upload_area}
        <div class="file-list glass-box" id="list">{file_rows}</div>
    </div>

    <div id="previewModal" class="modal"><div class="modal-content"><span class="modal-close" onclick="closePreview()">&times;</span><div id="previewBody" style="width:100%; height:100%; display:flex; justify-content:center; align-items:center;"></div></div></div>
    
    <div id="treeModal" class="modal">
        <div class="modal-content" style="flex-direction:column; background:#111; padding:20px; border-radius:12px; border:1px solid var(--border); width:90%; max-width:450px; height:70%;">
            <h3 id="tree-title" style="margin:0 0 15px 0; color:#fff;">Select Destination</h3>
            <div id="tree-list" style="flex:1; overflow-y:auto; background:#050505; border:1px solid #333; border-radius:8px; padding:10px;"></div>
            <div style="margin-top:15px; display:flex; gap:10px; width:100%; justify-content:flex-end;">
                <button class="btn" onclick="document.getElementById('treeModal').style.display='none'">Cancel</button>
                <button class="btn btn-action" onclick="confirmTreeAction()">Confirm</button>
            </div>
        </div>
    </div>

    <div id="logModal" class="modal">
        <div class="modal-content" style="flex-direction:column; background:#111; padding:20px; border-radius:12px; border:1px solid var(--border); width:80%; height:80%;">
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:15px;">
                <h3 style="margin:0; color:#fff;">Access Logs</h3>
                <div style="display:flex; gap:10px;">
                    <a href="/download_logs" class="btn" style="background:#222; border-color:#444;">📥 Download</a>
                    <button class="btn" style="background:rgba(255,0,0,0.1); color:#ff4444; border-color:#600;" onclick="clearLogs()">🗑️ Clear</button>
                </div>
            </div>
            <textarea readonly id="log-viewer" style="width:100%; height:85%; background:#050505; color:#0f0; border:1px solid #333; padding:15px; font-family:monospace; font-size:12px; resize:none; border-radius:8px; outline:none; box-sizing:border-box;">{log_data}</textarea>
            <div style="margin-top:15px; display:flex; justify-content:flex-end;">
                <button class="btn" onclick="document.getElementById('logModal').style.display='none'">Close</button>
            </div>
        </div>
    </div>

    <div id="editModal" class="modal">
        <div class="modal-content" style="flex-direction:column; background:#111; padding:20px; border-radius:12px; border:1px solid var(--border); width:80%; height:80%;">
            <h3 id="edit-name" style="margin:0 0 15px 0; color:#fff;"></h3>
            <textarea id="edit-box" style="width:100%; height:80%; background:#050505; color:#0f0; border:1px solid #333; padding:15px; font-family:monospace; font-size:14px; resize:none; border-radius:8px; outline:none; box-sizing:border-box;"></textarea>
            <div style="margin-top:15px; display:flex; gap:10px; width:100%; justify-content:flex-end;">
                <button class="btn" onclick="document.getElementById('editModal').style.display='none'">Cancel</button>
                <button class="btn btn-action" onclick="saveEdit()">Save Changes</button>
            </div>
        </div>
    </div>

    <script>
        const currentDir = "{current_dir}";
        
        function handleItemClick(url, type, lockId) {{
            if (lockId) {{
                // استراتژی پرسش مجدد: کوکی قبلی را به صورت اجباری پاک می‌کنیم
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                
                let p = prompt("🔒 This item is Locked. Please enter password:");
                if (p) {{
                    document.cookie = "lock_" + lockId + "=" + p + ";path=/";
                }} else {{
                    return; // اگر کنسل کرد، هیچ اتفاقی نمی‌افتد
                }}
            }}
            
            if (type === 'download') {{
                window.location.href = url;
            }} else {{
                openPreview(url, type);
            }}
        }}

        function doSearch() {{
            let q = document.getElementById('search').value.toLowerCase();
            document.querySelectorAll('.file-item').forEach(item => {{
                let name = item.getAttribute('data-name').toLowerCase();
                item.style.display = (name.includes(q) || name === '..') ? 'flex' : 'none';
            }});
        }}
        function toggleMenu(id) {{ document.querySelectorAll('.dropdown-content').forEach(d => {{ if(d.id !== id) d.classList.remove('show'); }}); document.getElementById(id).classList.toggle('show'); }}
        window.onclick = (e) => {{ if (!e.target.matches('.kebab-btn')) document.querySelectorAll('.dropdown-content').forEach(d => d.classList.remove('show')); }}
        
        function openPreview(url, type) {{
            const body = document.getElementById('previewBody'); body.innerHTML = ''; document.getElementById('previewModal').style.display = 'flex';
            if (type === 'image') body.innerHTML = `<img src="${{url}}">`;
            else if (type === 'video') body.innerHTML = `<video controls autoplay style="width:100%;"><source src="${{url}}"></video>`;
            else if (type === 'audio') body.innerHTML = `<audio controls autoplay><source src="${{url}}"></audio>`;
            else if (type === 'pdf') body.innerHTML = `<iframe src="${{url}}" style="width:100%; height:100%; background:#fff;"></iframe>`;
            else window.location.href = url;
        }}
        function closePreview() {{ document.getElementById('previewModal').style.display = 'none'; document.getElementById('previewBody').innerHTML = ''; }}
        
        let treeAction = ''; let treeTarget = ''; let treeSelected = null;
        function openTreeModal(act, tgt) {{
            treeAction = act; treeTarget = tgt; treeSelected = null;
            document.getElementById('tree-title').innerText = (act === 'move' ? 'Move ' : 'Copy ') + tgt;
            document.getElementById('treeModal').style.display = 'flex';
            document.getElementById('tree-list').innerHTML = '<div style="color:#888;text-align:center;padding:20px;">Loading folders...</div>';
            
            fetch('/action', {{method:'POST', body:new URLSearchParams({{action:'get_tree'}})}}).then(r=>r.json()).then(dirs => {{
                let h = '';
                dirs.forEach(d => {{
                    let pad = d === '/' ? 0 : (d.split('/').length - 1) * 20;
                    let name = d === '/' ? 'Root ( / )' : d.split('/').pop();
                    h += `<div class="tree-item" style="padding-left:${{pad + 15}}px" onclick="selectTreeItem(this, '${{d}}')">📁 ${{name}}</div>`;
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
            if(treeSelected === null) return alert('Please select a destination folder.');
            fetch('/action', {{method:'POST', body:new URLSearchParams({{action:treeAction, target:treeTarget, dir:currentDir, dest:treeSelected}})}}).then(()=>location.reload());
        }}

        function clearLogs() {{ if(confirm('Clear all logs?')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'clear_logs'}}) }}).then(()=>location.reload()); }}
        function createFolder() {{ let n = prompt("Folder Name:"); if(n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'mkdir', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function createFile() {{ let n = prompt("File Name (e.g. index.html):"); if(n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'mkfile', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function deleteItem(n) {{ if(confirm('Delete ' + n + '?')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'delete', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function renameItem(n) {{ let nn = prompt("Enter new name for: " + n, n); if(nn && nn !== n) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'rename', target:n, new_name:nn, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function moveItem(n) {{ openTreeModal('move', n); }}
        function copyItem(n) {{ openTreeModal('copy', n); }}
        function lockItem(n) {{ let pwd = prompt("Set Password (empty to unlock):"); if(pwd !== null) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'lock_item', target:n, dir:currentDir, pwd:pwd}}) }}).then(()=>location.reload()); }}
        
        function shareItem(n) {{ fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share', target:n, dir:currentDir}}) }}).then(r=>r.text()).then(l=>{{ prompt("Public Link:", window.location.origin+l); location.reload(); }}); }}
        function limitedShareItem(n) {{ let limit = prompt("Downloads limit:", "1"); if(limit && parseInt(limit)>0) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share_limit', target:n, dir:currentDir, limit:parseInt(limit)}}) }}).then(r=>r.text()).then(l=>{{ prompt("Link:", window.location.origin+l); location.reload(); }}); }}
        function pwdShareItem(n) {{ let pwd = prompt("Set password:"); if(pwd) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'share_pwd', target:n, dir:currentDir, pwd:pwd}}) }}).then(r=>r.text()).then(l=>{{ prompt("Link:", window.location.origin+l); location.reload(); }}); }}
        function renewItem(n) {{ if(confirm('Renew link for ' + n + '?')) fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'renew', target:n, dir:currentDir}}) }}).then(r=>r.text()).then(l=>{{ prompt("New Link:", window.location.origin+l); location.reload(); }}); }}
        function unshareItem(n) {{ fetch('/action', {{method:'POST', body: new URLSearchParams({{action:'unshare', target:n, dir:currentDir}}) }}).then(()=>location.reload()); }}
        function viewLink(tk) {{ prompt("Shared Link:", window.location.origin + "/p/" + tk); }}

        function editItem(n, lockId) {{
            if (lockId) {{
                document.cookie = "lock_" + lockId + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                let p = prompt("🔒 This item is Locked. Please enter password:");
                if (p) document.cookie = "lock_" + lockId + "=" + p + ";path=/";
                else return;
            }}
            fetch('/download/' + currentDir + '/' + n).then(r => r.text()).then(t => {{
                document.getElementById('edit-name').innerText = "Editing: " + n;
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
            input.onchange = (e) => {{
                const fd = new FormData(); for(let f of e.target.files) fd.append('file', f);
                document.getElementById('progress-wrapper').style.display = 'block';
                const xhr = new XMLHttpRequest(); xhr.open('POST', '/upload?dir='+encodeURIComponent(currentDir), true);
                xhr.upload.onprogress = (ev) => {{ document.getElementById('progress-bar').style.width = Math.round((ev.loaded/ev.total)*100) + '%'; }};
                xhr.onload = () => location.reload(); xhr.send(fd);
            }};
        }}
    </script>
</body>
</html>
"""

LOGIN_HTML = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title><style>""" + COMMON_STYLE + """body {{ display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }} .login-card {{ padding: 40px; width: 320px; text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }} input {{ width: 100%; padding: 14px; margin: 25px 0; background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: white; border-radius: 10px; box-sizing: border-box; outline: none; }} button {{ width: 100%; padding: 14px; background: #fff; color: #000; border: none; border-radius: 10px; cursor: pointer; font-weight: 800; text-transform: uppercase; }}</style></head><body><div class="login-card glass-box"><h2 style="color:#fff;">{site_name}</h2><form method="POST" action="/login"><input type="password" name="password" placeholder="••••••••" required autofocus><button type="submit">Unlock</button></form></div></body></html>"""

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
            self._send_resp(f'<style>{COMMON_STYLE}</style><body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;"><div class="glass-box" style="padding:40px;text-align:center;"><h1 style="color:var(--accent-red);margin:0;">🚫 ACCESS DENIED</h1><p style="color:var(--subtext);margin-top:15px;">Your IP has been temporarily blocked for 24 hours.</p></div></body>')
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
                        self._send_resp(f'<style>{COMMON_STYLE}</style><body style="display:flex;justify-content:center;align-items:center;height:100vh;"><script>let p=prompt("Password Required:");if(p)window.location.href="?pwd="+p;else document.body.innerHTML="Access Denied";</script></body>')
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
                    self._send_resp(f'<script>let p=prompt("Item Locked. Password:"); if(p){{ document.cookie="lock_{h}="+p+";path=/"; location.reload(); }} else history.back();</script>')
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
                rec_fail(self.client_address[0]); self.send_error(401); return
                
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
        admin_btn = '<button class="btn btn-action" onclick="createFolder()">+ New Folder</button><button class="btn btn-action" onclick="createFile()" style="margin-left:10px;">+ New File</button>' if role == 'admin' else ''
        admin_log_btn = '<button class="btn" style="background:rgba(0,255,0,0.1); color:#0f0;" onclick="document.getElementById(\'logModal\').style.display=\'flex\'">📜 Logs</button>' if role == 'admin' else ''
        up_area = '<div class="glass-box" id="drop-zone" style="padding:20px; text-align:center; margin-bottom:20px; cursor:pointer; border-style:dashed;"><p style="font-size:13px; color:var(--subtext);">Drop files to upload</p><input type="file" id="file-input" hidden multiple><div id="progress-wrapper" style="display:none; height:2px; background:#222; margin-top:10px;"><div id="progress-bar" style="width:0; height:100%; background:#fff;"></div></div></div>' if role == 'admin' else ''
        lns = load_json(LINKS_FILE); locks = load_json(LOCKS_FILE); log_content = ""
        if role == 'admin' and os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f: log_content = "".join(f.readlines())
        rows = ""
        if pts: rows += f'<div class="file-item" data-name=".."><div class="file-info"><span style="font-size:18px">🔙</span><a href="/?dir={urllib.parse.quote("/".join(pts[:-1]))}" class="file-name">..</a></div></div>'
        try: files = sorted(os.listdir(curr))
        except: files = []
        
        for f in files:
            if f in [CONFIG_FILE, LINKS_FILE, LOCKS_FILE, LOG_FILE, BLOCK_FILE]: continue
            full = os.path.join(curr, f); rel = self.get_rel(full); is_d = os.path.isdir(full); stat = os.stat(full)
            size = format_size(stat.st_size) if not is_d else "--"; date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
            
            lock_id = hashlib.md5(rel.encode()).hexdigest() if rel in locks else ""
            lock_info = f' <span style="color:#fa0; font-size:10px;">[Pass: {locks[rel]}]</span>' if rel in locks and role == 'admin' else (' 🔒' if rel in locks else '')
            
            if is_d:
                nx = f"{req_dir}/{f}".strip('/')
                dl_zip_click = f"handleItemClick('/zip/{nx}', 'download', '{lock_id}')"
                admin_h = f'<button onclick="{dl_zip_click}">📦 Download ZIP</button><button onclick="lockItem(\'{f}\')">🔒 Lock / Unlock</button><button onclick="renameItem(\'{f}\')">✏️ Rename</button><button onclick="copyItem(\'{f}\')">📄 Copy</button><button onclick="moveItem(\'{f}\')">✂️ Move</button><button onclick="deleteItem(\'{f}\')" class="btn-del-text">🗑️ Delete</button>' if role == 'admin' else f'<button onclick="{dl_zip_click}">📦 Download ZIP</button>'
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info"><span>📁</span><a href="/?dir={urllib.parse.quote(nx)}" class="file-name">{f}{lock_info}</a></div><div class="file-meta"><span>{date}</span><span>{size}</span></div><div class="actions"><button class="kebab-btn" onclick="toggleMenu(\'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{admin_h}</div></div></div>'
            else:
                p_type = get_preview_type(f); dl = urllib.parse.quote(f"/{req_dir}/{f}".replace('//', '/'))
                p_type_str = p_type if p_type else 'download'
                p_click = f"handleItemClick('/download{dl}', '{p_type_str}', '{lock_id}')"
                
                share_badge = ""
                view_link_btn = ""
                for tk, data in lns.items():
                    if (data.get('target') if isinstance(data, dict) else data) == rel:
                        pwd_hint = f" (Pass: {data.get('pwd')})" if isinstance(data, dict) and data.get('pwd') else ""
                        share_badge = f'<span style="color:var(--accent-red); font-size:9px; margin-left:8px;">● Shared{pwd_hint if role == "admin" else ""}</span>'
                        view_link_btn = f'<button onclick="viewLink(\'{tk}\')">👁️ View Link</button>'
                        break
                        
                is_text = f.split('.')[-1].lower() in ['txt', 'md', 'py', 'json', 'html', 'css', 'js', 'conf', 'sh']
                
                if role == 'admin':
                    s_btns = f'{view_link_btn}<button onclick="renewItem(\'{f}\')">🔄 Renew Link</button><button onclick="unshareItem(\'{f}\')">🚫 Unshare</button>' if share_badge else f'<button onclick="shareItem(\'{f}\')">🔗 Share Unlimited</button><button onclick="limitedShareItem(\'{f}\')">⏳ Limited Share</button><button onclick="pwdShareItem(\'{f}\')">🔑 Share (Password)</button>'
                    edit_btn = f'<button onclick="editItem(\'{f}\', \'{lock_id}\')">📝 Edit</button>' if is_text else ""
                    admin_h = f'{s_btns}{edit_btn}<button onclick="lockItem(\'{f}\')">🔒 Lock / Unlock</button><button onclick="renameItem(\'{f}\')">✏️ Rename</button><button onclick="copyItem(\'{f}\')">📄 Copy</button><button onclick="moveItem(\'{f}\')">✂️ Move</button><button onclick="deleteItem(\'{f}\')" class="btn-del-text">🗑️ Delete</button>'
                else: 
                    admin_h = ''
                    
                dl_btn = f'<button onclick="handleItemClick(\'/download{dl}\', \'download\', \'{lock_id}\')" class="btn">Download</button>'
                
                rows += f'<div class="file-item" data-name="{f}"><div class="file-info"><span>{get_icon(f, False)}</span><span onclick="{p_click}" class="file-name">{f}{lock_info}{share_badge}</span></div><div class="file-meta"><span>{date}</span><span>{size}</span></div><div class="actions" style="display:flex; align-items:center; gap:10px;">{dl_btn}<button class="kebab-btn" onclick="toggleMenu(\'m-{f}\')">⋮</button><div class="dropdown-content" id="m-{f}">{admin_h}</div></div></div>'
        
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
        with open(CONFIG_FILE, "w", encoding="utf-8") as f: f.write(f"SITE_NAME={sn}\nADMIN_PWD={ap}\nGUEST_PWD={gp}\nPORT={pt}\nUPLOAD_DIR={sd}\n")
        if not os.path.exists(sd): os.makedirs(sd)
        print(f"\n[✔] Setup Complete! Run 'python your_file.py run' to start.")
    elif args.cmd == "run":
        cfg = load_config()
        if not cfg: return print("[!] Run setup first.")
        FileHubHandler.CONFIG = cfg
        with socketserver.ThreadingTCPServer(("", int(cfg['PORT'])), FileHubHandler) as h:
            print(f"[*] Hub live at port {cfg['PORT']}"); h.serve_forever()

if __name__ == "__main__": main()
