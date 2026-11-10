
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
import logging

from urllib.parse import urlparse


# =============================================
# VIDX CONFIGURATION
# =============================================

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

DOWNLOAD_FOLDER = os.path.join(
    app.root_path,
    "downloads"
)

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB


# =============================================
# SUPPORTED PLATFORMS
# =============================================

SUPPORTED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",

    "instagram.com",
    "www.instagram.com",

    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",

    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com"
}


# =============================================
# URL VALIDATION
# =============================================

def is_valid_video_url(url):

    try:
        parsed = urlparse(url)

        if parsed.scheme != "https":
            return False

        hostname = (parsed.hostname or "").lower()

        return hostname in SUPPORTED_DOMAINS

    except Exception:
        return False


# =============================================
# PLATFORM DETECTION
# =============================================

def detect_platform(url):

    hostname = urlparse(url).hostname or ""

    if "youtube" in hostname or hostname == "youtu.be":
        return "YouTube"

    if "instagram" in hostname:
        return "Instagram"

    if "facebook" in hostname or hostname == "fb.watch":
        return "Facebook"

    if "tiktok" in hostname:
        return "TikTok"

    return "Unknown"


# =============================================
# YT-DLP COMMON OPTIONS
# =============================================

def get_common_options():

    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 2,
        "restrictfilenames": True
    }


# =============================================
# HOME PAGE
# =============================================

@app.route("/")
def home():

    return render_template("index.html")


# =============================================
# HEALTH CHECK
# =============================================

@app.route("/healthz")
def health_check():

    return jsonify({
        "status": "healthy",
        "app": "VidX Downloader"
    }), 200


# =============================================
# VIDEO INFORMATION API
# =============================================

@app.route("/api/info", methods=["POST"])
def video_info():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()

    if not is_valid_video_url(url):

        return jsonify({
            "error": "Unsupported or invalid video URL."
        }), 400

    try:

        options = get_common_options()

        options.update({
            "skip_download": True
        })

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        # Duration

        duration = info.get("duration")

        if duration is not None:

            minutes, seconds = divmod(
                int(duration), 60
            )

            hours, minutes = divmod(
                minutes, 60
            )

            duration_text = (
                f"{hours}:{minutes:02}:{seconds:02}"
                if hours
                else f"{minutes}:{seconds:02}"
            )

        else:

            duration_text = "Unknown"

        # Available qualities

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

            "qualities": available_qualities,

            "platform": detect_platform(url)

        })

    except Exception:

        app.logger.exception(
            "Video information fetch failed"
        )

        return jsonify({

            "error": (
                "Video information could not be fetched. "
                "The video may be unavailable or the platform "
                "may require an unsupported access method."
            )

        }), 400


# =============================================
# VIDEO / AUDIO DOWNLOAD API
# =============================================

@app.route("/api/download", methods=["POST"])
def download_video():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()

    quality = str(
        data.get("quality", "720")
    ).strip()

    file_format = str(
        data.get("format", "mp4")
    ).lower().strip()


    # Validate URL

    if not is_valid_video_url(url):

        return jsonify({
            "error": "Unsupported or invalid video URL."
        }), 400


    # Validate quality

    allowed_qualities = [
        "360",
        "480",
        "720",
        "1080"
    ]

    if quality not in allowed_qualities:

        return jsonify({
            "error": "Invalid video quality."
        }), 400


    # Validate format

    if file_format not in ["mp4", "mp3"]:

        return jsonify({
            "error": "Invalid file format."
        }), 400


    # Create temporary folder

    temp_folder = tempfile.mkdtemp(
        prefix="vidx_",
        dir=DOWNLOAD_FOLDER
    )


    # Common options

    options = get_common_options()

    options.update({

        "outtmpl": os.path.join(
            temp_folder,
            "%(title).150s.%(ext)s"
        ),

        "max_filesize": MAX_CONTENT_LENGTH

    })


    # MP4 FORMAT

    if file_format == "mp4":

        options.update({

            "format": (
                f"bestvideo[height<={quality}][ext=mp4]+"
                f"bestaudio[ext=m4a]/"
                f"best[height<={quality}][ext=mp4]/"
                f"best[height<={quality}]/best"
            ),

            "merge_output_format": "mp4"

        })


    # MP3 FORMAT

    else:

        options.update({

            "format": "bestaudio/best",

            "postprocessors": [{

                "key": "FFmpegExtractAudio",

                "preferredcodec": "mp3",

                "preferredquality": "192"

            }]

        })


    try:

        # Download video/audio

        with yt_dlp.YoutubeDL(options) as ydl:

            ydl.download([url])


        # Find downloaded file

        downloaded_files = [

            os.path.join(temp_folder, name)

            for name in os.listdir(temp_folder)

            if not name.endswith(
                (".part", ".ytdl")
            )

            and os.path.isfile(
                os.path.join(temp_folder, name)
            )

        ]


        if not downloaded_files:

            raise Exception(
                "Downloaded file not found."
            )


        file_path = downloaded_files[0]


        # Send file

        response = send_file(

            file_path,

            as_attachment=True,

            download_name=os.path.basename(
                file_path
            )

        )


        # Cleanup after response

        response.call_on_close(

            lambda: shutil.rmtree(
                temp_folder,
                ignore_errors=True
            )

        )

        return response


    except Exception:

        app.logger.exception(
            "Video download failed"
        )

        shutil.rmtree(
            temp_folder,
            ignore_errors=True
        )

        return jsonify({

            "error": (
                "Download failed. Check video availability, "
                "platform permissions, quality and FFmpeg."
            )

        }), 400


# =============================================
# APPLICATION START
# =============================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
