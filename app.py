
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
from urllib.parse import urlparse


app = Flask(__name__)


# ==============================
# VIDX CONFIGURATION
# ==============================

DOWNLOAD_FOLDER = os.path.join(
    app.root_path,
    "downloads"
)

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


# ==============================
# YOUTUBE URL VALIDATION
# ==============================

def is_valid_youtube_url(url):

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and parsed.hostname in [
                "youtube.com",
                "www.youtube.com",
                "m.youtube.com",
                "youtu.be"
            ]
        )

    except Exception:
        return False


# ==============================
# HOME PAGE
# ==============================

@app.route("/")
def home():
    return render_template("index.html")


# ==============================
# VIDEO INFORMATION API
# ==============================

@app.route("/api/info", methods=["POST"])
def video_info():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()

    if not is_valid_youtube_url(url):
        return jsonify({
            "error": "Please enter a valid YouTube URL."
        }), 400

    try:

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

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

        # Available video qualities
        available_qualities = sorted({
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

            "qualities": available_qualities

        })

    except Exception as error:

        print("Video information error:", error)

        return jsonify({
            "error": "Video information fetch nahi ho payi."
        }), 400


# ==============================
# VIDEO DOWNLOAD API
# ==============================

@app.route("/api/download", methods=["POST"])
def download_video():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()

    quality = str(data.get("quality", "720")).strip()

    file_format = data.get("format", "mp4").lower()


    # Validate URL

    if not is_valid_youtube_url(url):
        return jsonify({
            "error": "Invalid YouTube URL."
        }), 400


    # Validate quality

    allowed_qualities = ["360", "480", "720", "1080"]

    if quality not in allowed_qualities:
        return jsonify({
            "error": "Invalid video quality."
        }), 400


    # Validate format

    if file_format not in ["mp4", "mp3"]:
        return jsonify({
            "error": "Invalid file format."
        }), 400


    # Create temporary download folder

    temp_folder = tempfile.mkdtemp(
        prefix="vidx_",
        dir=DOWNLOAD_FOLDER
    )


    # Select download format

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


    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            ydl.download([url])


        # Find downloaded file

        downloaded_files = [
            os.path.join(temp_folder, name)
            for name in os.listdir(temp_folder)
            if not name.endswith((".part", ".ytdl"))
        ]

        if not downloaded_files:
            raise Exception("Downloaded file not found.")

        file_path = downloaded_files[0]

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path)
        )

        # Remove temporary files after sending

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
            "error": (
                "Download failed. Check video availability, "
                "quality and FFmpeg installation."
            )
        }), 400


# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":

    app.run(debug=True)
