from flask import Flask, render_template_string, redirect, url_for
import os, subprocess, datetime, threading, logging
from rich.logging import RichHandler

# Configure Logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("hardlinks-finder")

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
    "is_scanning": False,
    "files_scanned": 0,
    "current_file": ""
}
cache_lock = threading.Lock()

def perform_scan():
    global cache
    with cache_lock:
        cache["is_scanning"] = True
        cache["files_scanned"] = 0
        cache["current_file"] = "Starting..."
    
    logger.info(f"🚀 Starting scan in {SEARCH_PATH}/{SEARCH_SUBDIR} for *.{FILE_EXTENSION} files")
    
    try:
        path_to_search = os.path.join(SEARCH_PATH, SEARCH_SUBDIR)
        cmd = f"find {path_to_search} -type f -name '*.{FILE_EXTENSION}' -printf '%i|%p|%s\\n' 2>/dev/null || true"
        
        # Use Popen to read line-by-line for "real-time" stats
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, text=True)
        
        files_by_name = {}
        count = 0
        
        for line in process.stdout:
            line = line.strip()
            if not line: continue
            
            try:
                inode, path, size = line.split('|')
                name = os.path.basename(path)
                if name not in files_by_name: files_by_name[name] = []
                files_by_name[name].append({'inode': inode, 'path': path, 'size': int(size)})
                
                count += 1
                # Update progress every 100 files to keep performance high
                if count % 1000 == 0:
                    logger.info(f"🔎 Indexed {count} files...")
                    with cache_lock:
                        cache["files_scanned"] = count
                        cache["current_file"] = name
            except ValueError:
                continue

        process.wait()
        logger.info(f"✅ Indexed {count} total files. Calculating duplicates...")

        splits = []
        total_wasted = 0
        for name, instances in files_by_name.items():
            if len(instances) > 1:
                by_inode = {}
                for inst in instances:
                    inode = inst['inode']
                    if inode not in by_inode: by_inode[inode] = []
                    by_inode[inode].append(inst['path'])
                
                unique_inodes = list(by_inode.keys())
                if len(unique_inodes) > 1: 
                    wasted = (len(unique_inodes) - 1) * instances[0]['size']
                    total_wasted += wasted
                    splits.append({
                        'name': name, 
                        'by_inode': by_inode, 
                        'size': instances[0]['size'],
                        'wasted': wasted
                    })
        
        splits.sort(key=lambda x: x['wasted'], reverse=True)
        
        with cache_lock:
            cache["splits"] = splits
            cache["total_wasted"] = total_wasted
            cache["files_scanned"] = count
            cache["last_scan"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"✨ Scan complete! Found {round(total_wasted / (1024**3), 2)} GB of potential savings.")
    except Exception as e:
        logger.error(f"❌ Scan failed: {e}")
    finally:
        with cache_lock:
            cache["is_scanning"] = False
            cache["current_file"] = "Done"

@app.route('/fix_links', methods=['POST'])
def fix_links():
    import json
    name = request.form.get("name")
    
    # Find the specific row in our cache
    entry = next((s for s in cache["splits"] if s["name"] == name), None)
    if not entry:
        return redirect(url_for('index'))

    # Hardlinking Logic
    # 1. Pick the first inode's first path as the "Master Source"
    unique_inodes = list(entry['by_inode'].keys())
    master_inode = unique_inodes[0]
    master_source = entry['by_inode'][master_inode][0]
    
    # 2. For every OTHER unique inode, and every path within them...
    errors = []
    success_count = 0
    
    for other_inode in unique_inodes[1:]:
        for target_path in entry['by_inode'][other_inode]:
            try:
                # ln -f [source] [target] 
                # replaces target with a hardlink to source atomically
                subprocess.check_call(["ln", "-f", master_source, target_path])
                success_count += 1
            except subprocess.CalledProcessError as e:
                errors.append(f"Failed to link {os.path.basename(target_path)}: {str(e)}")
            except Exception as e:
                errors.append(f"System error on {os.path.basename(target_path)}: {str(e)}")

    if errors:
        logger.error(f"❌ Fix hardlinks failed for {name}: {errors}")
    else:
        logger.info(f"✅ Successfully merged duplicates for {name} ({success_count} links created)")
    
    # Trigger a background scan to update the UI with new results
    threading.Thread(target=perform_scan).start()
    
    return redirect(url_for('index'))

@app.route('/')
def index():
    total_gb = round(cache["total_wasted"] / (1024**3), 2)
    
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HardlinkFinder</title>
            {% if is_scanning %}
            <meta http-equiv="refresh" content="3">
            {% endif %}
            <style>
                body { background: #0f0f0f; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; padding: 40px; }
                .container { max-width: 1300px; margin: auto; }
                .header-flex { display: flex; justify-content: space-between; align-items: stretch; margin-bottom: 30px; }
                .stats { background: #1a1a1a; padding: 20px; border-radius: 8px; border-left: 5px solid #0078d4; flex-grow: 1; margin-right: 20px; }
                .controls { background: #1a1a1a; padding: 20px; border-radius: 8px; text-align: center; min-width: 250px; display: flex; flex-direction: column; justify-content: center; position: relative; overflow: hidden; }
                h1 { margin: 0; color: #fff; letter-spacing: 1px; }
                .scan-btn { background: #0078d4; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: background 0.2s; z-index: 1; }
                .scan-btn:hover { background: #005a9e; }
                .scan-btn:disabled { background: #333; color: #888; cursor: not-allowed; }
                
                .fix-btn { background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.85em; transition: background 0.2s; white-space: nowrap; }
                .fix-btn:hover { background: #218838; }

                /* Progress Bar Animation */
                .progress-container { width: 100%; height: 4px; background: #252525; position: absolute; bottom: 0; left: 0; }
                .progress-bar { height: 100%; background: #0078d4; width: 30%; position: absolute; animation: progress-swipe 2s infinite ease-in-out; }
                @keyframes progress-swipe {
                    0% { left: -30%; }
                    100% { left: 100%; }
                }

                table { width: 100%; border-collapse: collapse; background: #1a1a1a; border-radius: 8px; overflow: hidden; }
                th { background: #252525; padding: 15px; text-align: left; color: #888; text-transform: uppercase; font-size: 0.8em; }
                td { padding: 15px; border-top: 1px solid #333; vertical-align: top; }
                tr:hover { background: #222; }
                .path-tag { background: #333; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-bottom: 4px; display: block; color: #00a2ed; }
                .wasted { color: #ff4d4d; font-weight: bold; }
                .scan-stats { font-size: 0.8em; color: #888; margin-top: 8px; z-index: 1; }
                .current-file { font-size: 0.7em; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 210px; margin-top: 5px; }
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
                                {% if is_scanning %}INDEXING FILES...{% else %}START SCAN{% endif %}
                            </button>
                        </form>
                        {% if is_scanning %}
                        <div class="scan-stats">Files found: <strong>{{ files_scanned }}</strong></div>
                        <div class="current-file">{{ current_file }}</div>
                        <div class="progress-container"><div class="progress-bar"></div></div>
                        {% else %}
                        <div class="scan-stats">Last Scan: {{ last_scan or 'Never' }}</div>
                        {% endif %}
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>File Name</th>
                            <th>Size</th>
                            <th>Locations (Grouped by Inode)</th>
                            <th>Wasted</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if not splits and not is_scanning %}
                        <tr><td colspan="5" style="text-align: center; color: #666; padding: 40px;">No duplicates found. Click "START SCAN" to begin.</td></tr>
                        {% endif %}
                        {% for s in splits %}
                        <tr>
                            <td style="font-size: 0.9em; max-width: 300px; word-break: break-all;">{{ s.name }}</td>
                            <td>{{ (s.size / (1024**3))|round(2) }} GB</td>
                            <td>
                                {% for inode, paths in s.by_inode.items() %}
                                <div style="margin-bottom: 15px; background: #222; padding: 10px; border-radius: 4px;">
                                    <div style="font-size: 0.7em; color: #666; margin-bottom: 5px;">INODE: {{ inode }}</div>
                                    {% for path in paths %}
                                    <span class="path-tag">{{ path }}</span>
                                    {% endfor %}
                                </div>
                                {% endfor %}
                            </td>
                            <td class="wasted">{{ (s.wasted / (1024**3))|round(2) }} GB</td>
                            <td>
                                <form action="/fix_links" method="post" onsubmit="return confirm('This will physically replace duplicate files with hardlinks to the first copy. Proceed?');">
                                    <input type="hidden" name="name" value="{{ s.name }}">
                                    <button type="submit" class="fix-btn">FIX HARDLINKS</button>
                                </form>
                            </td>
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
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)