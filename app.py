from flask import Flask, render_template_string
import os, subprocess, datetime, threading

app = Flask(__name__)

# Configuration from Environment Variables
SEARCH_PATH = os.environ.get("SEARCH_PATH", "/storage")
SEARCH_SUBDIR = os.environ.get("SEARCH_SUBDIR", "")
FILE_EXTENSION = os.environ.get("FILE_EXTENSION", "mkv")

# Global Cache
cache = {
    "splits": [],
    "total_wasted": 0,
    "last_scan": None,
    "is_scanning": False
}
cache_lock = threading.Lock()

def perform_scan():
    global cache
    with cache_lock:
        cache["is_scanning"] = True
    
    try:
        path_to_search = os.path.join(SEARCH_PATH, SEARCH_SUBDIR)
        cmd = f"find {path_to_search} -type f -name '*.{FILE_EXTENSION}' -printf '%i|%p|%s\\n'"
        output = subprocess.check_output(cmd, shell=True).decode().splitlines()
        
        files_by_name = {}
        for line in output:
            try:
                inode, path, size = line.split('|')
                name = os.path.basename(path)
                if name not in files_by_name: files_by_name[name] = []
                files_by_name[name].append({'inode': inode, 'path': path, 'size': int(size)})
            except ValueError:
                continue

        splits = []
        total_wasted = 0
        for name, instances in files_by_name.items():
            if len(instances) > 1:
                inodes = set(i['inode'] for i in instances)
                if len(inodes) > 1: 
                    wasted = (len(instances) - 1) * instances[0]['size']
                    total_wasted += wasted
                    splits.append({
                        'name': name, 
                        'instances': instances, 
                        'size': instances[0]['size'],
                        'wasted': wasted
                    })
        
        splits.sort(key=lambda x: x['wasted'], reverse=True)
        
        with cache_lock:
            cache["splits"] = splits
            cache["total_wasted"] = total_wasted
            cache["last_scan"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    finally:
        with cache_lock:
            cache["is_scanning"] = False

@app.route('/')
def index():
    total_gb = round(cache["total_wasted"] / (1024**3), 2)
    
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HardlinkFinder</title>
            <style>
                body { background: #0f0f0f; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; padding: 40px; }
                .container { max-width: 1200px; margin: auto; }
                .header-flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
                .stats { background: #1a1a1a; padding: 20px; border-radius: 8px; border-left: 5px solid #0078d4; flex-grow: 1; margin-right: 20px; }
                .controls { background: #1a1a1a; padding: 20px; border-radius: 8px; text-align: center; min-width: 200px; }
                h1 { margin: 0; color: #fff; letter-spacing: 1px; }
                .scan-btn { background: #0078d4; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
                .scan-btn:hover { background: #005a9e; }
                .scan-btn:disabled { background: #444; cursor: not-allowed; }
                table { width: 100%; border-collapse: collapse; background: #1a1a1a; border-radius: 8px; overflow: hidden; }
                th { background: #252525; padding: 15px; text-align: left; color: #888; text-transform: uppercase; font-size: 0.8em; }
                td { padding: 15px; border-top: 1px solid #333; vertical-align: top; }
                tr:hover { background: #222; }
                .path-tag { background: #333; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-bottom: 4px; display: block; color: #00a2ed; }
                .wasted { color: #ff4d4d; font-weight: bold; }
                .last-scan { font-size: 0.8em; color: #666; margin-top: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-flex">
                    <div class="stats">
                        <h1>HardlinkFinder</h1>
                        <p>Potential Savings: <span class="wasted">{{ total_gb }} GB</span></p>
                    </div>
                    <div class="controls">
                        <form action="/scan" method="post">
                            <button type="submit" class="scan-btn" {% if is_scanning %}disabled{% endif %}>
                                {% if is_scanning %}Scanning...{% else %}Start Scan{% endif %}
                            </button>
                        </form>
                        <div class="last-scan">Last Scan: {{ last_scan or 'Never' }}</div>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>File Name</th>
                            <th>Size</th>
                            <th>Locations (Duplicate Inodes)</th>
                            <th>Wasted</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if not splits and not is_scanning %}
                        <tr><td colspan="4" style="text-align: center; color: #666; padding: 40px;">No scan data available. Click "Start Scan" to begin.</td></tr>
                        {% endif %}
                        {% for s in splits %}
                        <tr>
                            <td>{{ s.name }}</td>
                            <td>{{ (s.size / (1024**3))|round(2) }} GB</td>
                            <td>
                                {% for i in s.instances %}
                                <span class="path-tag">{{ i.path }}</span>
                                {% endfor %}
                            </td>
                            <td class="wasted">{{ (s.wasted / (1024**3))|round(2) }} GB</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
    """, splits=cache["splits"], total_gb=total_gb, last_scan=cache["last_scan"], is_scanning=cache["is_scanning"])

@app.route('/scan', methods=['POST'])
def trigger_scan():
    if not cache["is_scanning"]:
        # Run scan in a background thread so the web request doesn't timeout
        thread = threading.Thread(target=perform_scan)
        thread.start()
    return index()

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)