from flask import Flask, render_template_string
import os, subprocess

app = Flask(__name__)

# Configuration from Environment Variables
SEARCH_PATH = os.environ.get("SEARCH_PATH", "/storage")
# Optional: specific subdirectory or pattern to avoid FUSE double-counting (e.g., "disk*")
SEARCH_SUBDIR = os.environ.get("SEARCH_SUBDIR", "")
# File extension to search for
FILE_EXTENSION = os.environ.get("FILE_EXTENSION", "mkv")

def get_data():
    # Construct the search path
    path_to_search = os.path.join(SEARCH_PATH, SEARCH_SUBDIR)
    
    # Find all matching files, get Inode, Path, and Size
    cmd = f"find {path_to_search} -type f -name '*.{FILE_EXTENSION}' -printf '%i|%p|%s\\n'"
    try:
        output = subprocess.check_output(cmd, shell=True).decode().splitlines()
    except Exception as e:
        print(f"Error running find: {e}")
        return [], 0
    
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
                # Calculation: (Total instances - 1) * size = wasted space
                wasted = (len(instances) - 1) * instances[0]['size']
                total_wasted += wasted
                splits.append({
                    'name': name, 
                    'instances': instances, 
                    'size': instances[0]['size'],
                    'wasted': wasted
                })
    
    # Sort by biggest waste first
    splits.sort(key=lambda x: x['wasted'], reverse=True)
    return splits, total_wasted

@app.route('/')
def index():
    splits, total_wasted = get_data()
    total_gb = round(total_wasted / (1024**3), 2)
    
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HardlinkFinder</title>
            <style>
                body { background: #0f0f0f; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; padding: 40px; }
                .container { max-width: 1200px; margin: auto; }
                .stats { background: #1a1a1a; padding: 20px; border-radius: 8px; border-left: 5px solid #0078d4; margin-bottom: 30px; }
                h1 { margin: 0; color: #fff; letter-spacing: 1px; }
                table { width: 100%; border-collapse: collapse; background: #1a1a1a; border-radius: 8px; overflow: hidden; }
                th { background: #252525; padding: 15px; text-align: left; color: #888; text-transform: uppercase; font-size: 0.8em; }
                td { padding: 15px; border-top: 1px solid #333; vertical-align: top; }
                tr:hover { background: #222; }
                .path-tag { background: #333; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin-right: 5px; color: #00a2ed; }
                .wasted { color: #ff4d4d; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="stats">
                    <h1>HardlinkFinder</h1>
                    <p>Potential Savings: <span class="wasted">{{ total_gb }} GB</span></p>
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
                        {% for s in splits %}
                        <tr>
                            <td>{{ s.name }}</td>
                            <td>{{ (s.size / (1024**3))|round(2) }} GB</td>
                            <td>
                                {% for i in s.instances %}
                                <div class="path-tag">{{ i.path }}</div>
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
    """, splits=splits, total_gb=total_gb)

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)