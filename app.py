
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)

import yt_dlp
import os
import tempfile
import shutil
import requests

from urllib.parse import urlparse, unquote
from werkzeug.utils import secure_filename


app = Flask(__name__)

# =====================================
# VIDX CONFIGURATION
# =====================================

DOWNLOAD_FOLDER = os.path.join(app.root_path, "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Only explicitly trusted hosts for direct MP4 links.
DIRECT_VIDEO_HOSTS = {
    "samplelib.com",
    "www.samplelib.com",
    "storage.googleapis.com"
}


# =====================================
# URL VALIDATION
# =====================================

def get_url_type(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme != "https" or not parsed.hostname:
            return None

        host = parsed.hostname.lower()

        youtube_hosts = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be"
        }

        if host in youtube_hosts:
            return "youtube"

        if (
            host in DIRECT_VIDEO_HOSTS
            and parsed.path.lower().endswith(".mp4")
            and not parsed.username
            and not parsed.password
        ):
            return "direct"

        return None

    except Exception:
        return None


# =====================================
# DIRECT MP4 INFORMATION
# =====================================

def get_direct_video_info(url):
    response = requests.get(
        url,
        stream=True,
        timeout=(10, 20),
        allow_redirects=False,
        headers={"User-Agent": "VidX/1.0"}
    )

    try:
        if response.status_code != 200:
            raise ValueError("Direct video URL is unavailable.")

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "video/mp4" not in content_type:
            raise ValueError("URL does not serve an MP4 video.")

        content_length = int(
            response.headers.get("Content-Length", 0)
        )

        if content_length > MAX_FILE_SIZE:
            raise ValueError("Video exceeds the 100 MB limit.")

        filename = os.path.basename(
            unquote(urlparse(url).path)
        )

        filename = secure_filename(filename) or "VidX_Video.mp4"

        return {
            "success": True,
            "title": filename,
            "thumbnail": "",
            "duration": "Unknown",
            "qualities": [360, 480, 720, 1080],
            "source": "direct"
        }

    finally:
        response.close()


# =====================================
# HOME PAGE
# =====================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================
# HEALTH CHECK
# =====================================

@app.route("/healthz")
def health_check():
    return jsonify({
        "app": "VidX Downloader",
        "status": "healthy"
    })


# =====================================
# VIDEO INFORMATION API
# =====================================

@app.route("/api/info", methods=["POST"])
def video_info():

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()

    url_type = get_url_type(url)

    if not url_type:
        return jsonify({
            "error": "Unsupported or invalid video URL."
        }), 400

    try:

        if url_type == "direct":
            return jsonify(get_direct_video_info(url))

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

        duration = info.get("duration")

        if duration is not None:
            minutes, seconds = divmod(int(duration), 60)
            hours, minutes = divmod(minutes, 60)

            duration_text = (
                f"{hours}:{minutes:02}:{seconds:02}"
                if hours
                else f"{minutes}:{seconds:02}"
            )
        else:
            duration_text = "Unknown"

        qualities = sorted({
            int(item["height"])
            for item in info.get("formats", [])
            if item.get("height")
            and item.get("vcodec") != "none"
        }, reverse=True)

        return jsonify({
            "success": True,
            "title": info.get("title", "Unknown"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": duration_text,
            "qualities": qualities,
            "source": "youtube"
        })

    except Exception as error:
        print("Video information error:", error)

        return jsonify({
            "error": "Video information fetch nahi ho payi."
        }), 400


# =====================================
# DIRECT MP4 DOWNLOAD
# =====================================

def download_direct_mp4(url, temp_folder):

    response = requests.get(
        url,
        stream=True,
        timeout=(10, 30),
        allow_redirects=False,
        headers={"User-Agent": "VidX/1.0"}
    )

    if response.status_code != 200:
        response.close()
        raise ValueError("Unable to access the MP4 file.")

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if "video/mp4" not in content_type:
        response.close()
        raise ValueError("URL is not a valid MP4 video.")

    content_length = int(
        response.headers.get("Content-Length", 0)
    )

    if content_length > MAX_FILE_SIZE:
        response.close()
        raise ValueError("Maximum download size is 100 MB.")

    filename = os.path.basename(
        unquote(urlparse(url).path)
    )

    filename = secure_filename(filename) or "VidX_Video.mp4"

    file_path = os.path.join(temp_folder, filename)
    downloaded = 0

    try:
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue

                downloaded += len(chunk)

                if downloaded > MAX_FILE_SIZE:
                    raise ValueError("Maximum download size is 100 MB.")

                file.write(chunk)

    finally:
        response.close()

    return file_path


# =====================================
# VIDEO / AUDIO DOWNLOAD API
# =====================================

@app.route("/api/download", methods=["POST"])
def download_video():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()
    quality = str(data.get("quality", "720")).strip()
    file_format = data.get("format", "mp4").lower()

    url_type = get_url_type(url)

    if not url_type:
        return jsonify({
            "error": "Unsupported or invalid video URL."
        }), 400

    if quality not in ["360", "480", "720", "1080"]:
        return jsonify({
            "error": "Invalid video quality."
        }), 400

    if file_format not in ["mp4", "mp3"]:
        return jsonify({
            "error": "Invalid file format."
        }), 400

    # Direct MP4 links
    if url_type == "direct" and file_format == "mp3":
        return jsonify({
            "error": "MP3 conversion is currently available only for YouTube URLs."
        }), 400

    temp_folder = tempfile.mkdtemp(
        prefix="vidx_",
        dir=DOWNLOAD_FOLDER
    )

    try:

        if url_type == "direct":

            file_path = download_direct_mp4(
                url,
                temp_folder
            )

        else:

            if file_format == "mp4":

                format_selector = (
                    f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[height<={quality}][ext=mp4]/"
                    f"best[height<={quality}]"
                )

                options = {
                    "format": format_selector,
                    "outtmpl": os.path.join(
                        temp_folder,
                        "%(title)s.%(ext)s"
                    ),
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True
                }

            else:

                options = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(
                        temp_folder,
                        "%(title)s.%(ext)s"
                    ),
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192"
                    }]
                }

            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])

            downloaded_files = [
                os.path.join(temp_folder, name)
                for name in os.listdir(temp_folder)
                if not name.endswith((".part", ".ytdl"))
            ]

            if not downloaded_files:
                raise ValueError("Downloaded file not found.")

            file_path = downloaded_files[0]

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )

        response.call_on_close(
            lambda: shutil.rmtree(
                temp_folder,
                ignore_errors=True
            )
        )

        return response

    except Exception as error:

        print("Download error:", error)

        shutil.rmtree(
            temp_folder,
            ignore_errors=True
        )

        return jsonify({
            "error": str(error)
        }), 400


# =====================================
# RUN APPLICATION
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
