# HardlinkFinder

A lightweight, agnostic web dashboard to identify "wasted" space in your media library by finding identical files that have different inodes (duplicates that are not yet hardlinked).

Perfect for Unraid, Synology, or any Linux-based media server using split-level storage.

## 🚀 Features

- **Agnostic Design**: Works with any directory structure or file type.
- **Wasted Space Calculation**: Quantifies exactly how much storage you're losing to duplicates.
- **Deep Inode Analysis**: Uses the native Linux `find` command for fast, accurate results.
- **Modern Web UI**: Clean, dark-themed dashboard with real-time stats.
- **Docker Ready**: Runs as a non-privileged user with minimal footprint.
- **CI/CD Integrated**: Automatically builds and pushes to GHCR via GitHub Actions.

## 🐳 Docker Usage

The image is built on **Python 3.14-slim** for maximum performance and security.

```bash
docker run -d \
  --name hardlinks-finder \
  -p 5000:5000 \
  -v /your/media:/storage:ro \
  -e SEARCH_PATH=/storage \
  -e FILE_EXTENSION=mkv \
  ghcr.io/rickychan21/hardlinks-finder:latest
```

### Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SEARCH_PATH` | `/storage` | The root directory within the container to scan. |
| `SEARCH_SUBDIR` | (Empty) | Optional pattern to append to search (e.g., `disk*` for Unraid). |
| `FILE_EXTENSION`| `mkv` | The file extension to audit. |
| `PORT` | `5000` | The internal port the web server listens on. |

## 🏗️ Unraid Setup

1. Go to the **Docker** tab and click **Add Container**.
2. **Repository**: `ghcr.io/rickychan21/hardlinks-finder:latest`
3. **Network**: `Bridge`
4. **Port Mapping**: Map host port `5000` to container port `5000`.
5. **Path Mapping**: Map `/mnt/user/` (or `/mnt/`) to `/storage` (set to Read Only).
6. **(Optional)** Add an Variable:
   - Key: `SEARCH_SUBDIR`
   - Value: `disk*`
   - *Note: This helps find duplicates split across multiple physical drives.*

## 🛠️ Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python app.py
   ```
3. Access the UI at `http://localhost:5000`.

## 🛡️ Security

- **Non-Root**: The container runs as a non-privileged user (UID/GID 1000).
- **Read-Only Compatible**: The application only requires read access to your media.
- **Updated Tech**: Uses the latest stable Python 3.14 and Node.js 24 Actions.

---
*Built with ❤️ for the self-hosted packaging community.*
