import os
import uuid
import threading
import re
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
import yt_dlp


BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
MAX_CONCURRENT = 3


def create_app(testing=False):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key")

    downloads_state: dict[str, dict] = {}
    active_downloads: list[str] = []
    state_lock = threading.Lock()

    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = re.sub(r'_{2,}', "_", name)
        return name.strip("._ ")[:200]

    def get_available_format(formats: list[dict]) -> list[dict]:
        seen = set()
        available = []
        for f in formats:
            if f.get("height") and f.get("ext") in ("mp4", "webm"):
                key = (f["height"], f["ext"])
                if key not in seen:
                    seen.add(key)
                    available.append({
                        "id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "height": f["height"],
                        "fps": f.get("fps", 30),
                        "vcodec": f.get("vcodec", "unknown"),
                        "acodec": f.get("acodec", "unknown"),
                        "filesize": f.get("filesize", 0),
                    })
        available.sort(key=lambda x: x["height"], reverse=True)
        return available

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/info", methods=["POST"])
    def video_info():
        data = request.get_json(silent=True)
        if not data or not data.get("url"):
            return jsonify({"error": "URL is required"}), 400
        try:
            url = data["url"]
            if not url.startswith(("http://", "https://")):
                return jsonify({"error": "Invalid URL format"}), 400
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            formats = get_available_format(info.get("formats", []))
            return jsonify({
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "formats": formats,
            })
        except Exception as e:
            return jsonify({"error": f"Failed to fetch video info: {str(e)}"}), 400

    @app.route("/api/download", methods=["POST"])
    def start_download():
        data = request.get_json(silent=True)
        if not data or not data.get("url") or not data.get("format_id"):
            return jsonify({"error": "URL and format_id are required"}), 400
        with state_lock:
            if len(active_downloads) >= MAX_CONCURRENT:
                return jsonify({"error": "Too many active downloads. Wait for one to finish."}), 429

            download_id = uuid.uuid4().hex[:12]
            custom_name = data.get("filename", "").strip()
            filename = sanitize_filename(custom_name) if custom_name else download_id

            downloads_state[download_id] = {
                "id": download_id,
                "status": "pending",
                "progress": 0.0,
                "speed": "",
                "eta": 0,
                "total_bytes": 0,
                "downloaded_bytes": 0,
                "filename": "",
                "error": "",
                "title": data.get("title", "Video"),
            }
            active_downloads.append(download_id)

        def progress_hook(d):
            with state_lock:
                state = downloads_state.get(download_id)
                if not state:
                    return
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    downloaded = d.get("downloaded_bytes", 0)
                    state.update({
                        "status": "downloading",
                        "progress": (downloaded / total * 100) if total else 0,
                        "speed": d.get("speed", ""),
                        "eta": d.get("eta", 0),
                        "total_bytes": total,
                        "downloaded_bytes": downloaded,
                    })
                elif d["status"] == "finished":
                    state.update({
                        "status": "completed",
                        "progress": 100.0,
                        "filename": d.get("filename", ""),
                    })

        def run_download():
            try:
                outtmpl = str(DOWNLOADS_DIR / f"{filename}.%(ext)s")
                ydl_opts = {
                    "format": data["format_id"],
                    "outtmpl": outtmpl,
                    "progress_hooks": [progress_hook],
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([data["url"]])
                with state_lock:
                    state = downloads_state.get(download_id)
                    if state and state["status"] == "completed":
                        ext = data["format_id"]
                        expected = DOWNLOADS_DIR / f"{filename}.{ext}"
                        if expected.exists():
                            state["filename"] = expected.name
                            state["title"] = state.get("title", expected.stem)
            except Exception as e:
                with state_lock:
                    if download_id in downloads_state:
                        downloads_state[download_id].update({
                            "status": "error",
                            "error": str(e),
                        })
                for f in DOWNLOADS_DIR.iterdir():
                    if f.stem == filename or f.stem.startswith(filename):
                        f.unlink(missing_ok=True)
            finally:
                with state_lock:
                    if download_id in active_downloads:
                        active_downloads.remove(download_id)

        thread = threading.Thread(target=run_download, daemon=True)
        thread.start()

        return jsonify({"download_id": download_id, "status": "started"})

    @app.route("/api/status/<download_id>")
    def download_status(download_id):
        with state_lock:
            state = downloads_state.get(download_id)
            if not state:
                return jsonify({"error": "Download not found"}), 404
            state_copy = dict(state)
        return jsonify(state_copy)

    @app.route("/api/downloads")
    def list_downloads():
        with state_lock:
            completed = [
                dict(s) for s in downloads_state.values()
                if s["status"] == "completed"
            ]
        return jsonify({"downloads": completed})

    @app.route("/downloads/<path:filename>")
    def serve_file(filename):
        sanitized = Path(filename).name
        filepath = DOWNLOADS_DIR / sanitized
        if not filepath.exists():
            abort(404)
        return send_from_directory(DOWNLOADS_DIR, sanitized, as_attachment=True)

    return app


if __name__ == "__main__":
    app = create_app()
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    app.run(debug=True, port=5000)
