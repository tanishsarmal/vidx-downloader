
// =============================================
// VIDX - PREMIUM VIDEO DOWNLOADER
// COMPLETE JAVASCRIPT
// =============================================


// =============================================
// ELEMENTS
// =============================================

const videoUrl = document.getElementById("videoUrl");
const fetchBtn = document.getElementById("fetchBtn");
const downloadBtn = document.getElementById("downloadBtn");

const message = document.getElementById("message");
const downloadMessage = document.getElementById("downloadMessage");

const HISTORY_KEY = "vidx_download_history";
const THEME_KEY = "vidx_theme";


// =============================================
// STATUS MESSAGE HELPER
// =============================================

function showStatus(element, text, type = "loading") {
    if (!element) return;

    element.className = `status-${type}`;
    element.textContent = text;
}

function clearStatus(element) {
    if (!element) return;

    element.textContent = "";
    element.className = "";
}


// =============================================
// BUTTON LOADING HELPER
// =============================================

function setButtonLoading(button, loading, text) {
    if (!button) return;

    if (loading) {
        if (!button.classList.contains("loading")) {
            button.dataset.originalText = button.textContent.trim();
        }

        button.disabled = true;
        button.classList.add("loading");

        button.innerHTML = `
            <span class="vidx-spinner"></span>
            ${text}
        `;
    } else {
        button.disabled = false;
        button.classList.remove("loading");

        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}


// =============================================
// FETCH VIDEO INFORMATION
// =============================================

async function fetchVideo() {
    const url = videoUrl.value.trim();

    clearStatus(message);
    clearStatus(downloadMessage);

    if (!url) {
        showStatus(message, "Please enter a video URL.", "error");
        return;
    }

    setButtonLoading(fetchBtn, true, "Fetching video...");

    showStatus(
        message,
        "Please wait, fetching video information...",
        "loading"
    );

    try {
        const response = await fetch("/api/info", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to fetch video.");
        }

        document.getElementById("videoTitle").textContent =
            data.title || "Unknown";

        document.getElementById("videoDuration").textContent =
            data.duration || "Unknown";

        document.getElementById("thumbnail").src =
            data.thumbnail || "";

        // QUALITY OPTIONS

        const qualitySelect = document.getElementById("quality");

        qualitySelect.innerHTML = "";

        const allowedQualities = [360, 480, 720, 1080];

        const availableQualities = allowedQualities.filter(
            quality => (data.qualities || []).includes(quality)
        );

        if (availableQualities.length === 0) {
            availableQualities.push(360);
        }

        availableQualities.forEach(quality => {
            const option = document.createElement("option");

            option.value = quality;
            option.textContent = `${quality}p`;

            qualitySelect.appendChild(option);
        });

        qualitySelect.value =
            availableQualities.includes(720)
                ? "720"
                : String(Math.max(...availableQualities));

        qualitySelect.disabled = false;

        // SHOW VIDEO PREVIEW

        document.getElementById("videoPreview").style.display = "block";

        showStatus(
            message,
            "Video information fetched successfully!",
            "success"
        );

    } catch (error) {
        showStatus(
            message,
            error.message || "Something went wrong.",
            "error"
        );

    } finally {
        setButtonLoading(fetchBtn, false);
    }
}


// =============================================
// START VIDEO / AUDIO DOWNLOAD
// =============================================

async function startDownload() {
    const url = videoUrl.value.trim();

    const quality = document.getElementById("quality").value;
    const format = document.getElementById("format").value;

    clearStatus(downloadMessage);

    if (!url) {
        showStatus(downloadMessage, "Please enter a video URL.", "error");
        return;
    }

    setButtonLoading(downloadBtn, true, "Preparing download...");

    showStatus(
        downloadMessage,
        "Your download is being prepared...",
        "loading"
    );

    const progressContainer =
        document.getElementById("progressContainer");

    const progressFill =
        document.getElementById("progressFill");

    const progressPercent =
        document.getElementById("progressPercent");

    if (progressContainer) {
        progressContainer.style.display = "block";
    }

    if (progressFill) {
        progressFill.style.width = "0%";
    }

    if (progressPercent) {
        progressPercent.textContent = "0%";
    }

    try {
        const response = await fetch("/api/download", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                url,
                quality,
                format
            })
        });

        if (!response.ok) {
            let errorMessage = "Download failed.";

            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (_) {}

            throw new Error(errorMessage);
        }

        showStatus(
            downloadMessage,
            "Download ready. Transferring file...",
            "loading"
        );

        const totalSize = Number(
            response.headers.get("Content-Length")
        );

        const reader = response.body.getReader();
        const chunks = [];

        let receivedSize = 0;

        // READ DOWNLOAD STREAM

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            chunks.push(value);
            receivedSize += value.length;

            if (totalSize > 0) {
                const percent = Math.min(
                    99,
                    Math.round((receivedSize / totalSize) * 100)
                );

                if (progressFill) {
                    progressFill.style.width = `${percent}%`;
                }

                if (progressPercent) {
                    progressPercent.textContent = `${percent}%`;
                }
            }
        }

        // CREATE FILE

        const blob = new Blob(chunks, {
            type: format === "mp3" ? "audio/mpeg" : "video/mp4"
        });

        // GET FILENAME

        const contentDisposition =
            response.headers.get("Content-Disposition") || "";

        const filenameMatch = contentDisposition.match(
            /filename="?([^"]+)"?/i
        );

        const filename = filenameMatch
            ? filenameMatch[1]
            : `VidX_Download.${format}`;

        // DOWNLOAD FILE

        const downloadUrl = URL.createObjectURL(blob);

        const link = document.createElement("a");

        link.href = downloadUrl;
        link.download = filename;

        document.body.appendChild(link);
        link.click();
        link.remove();

        setTimeout(() => {
            URL.revokeObjectURL(downloadUrl);
        }, 1000);

        // COMPLETE PROGRESS

        if (progressFill) {
            progressFill.style.width = "100%";
        }

        if (progressPercent) {
            progressPercent.textContent = "100%";
        }

        showStatus(
            downloadMessage,
            "Download completed successfully!",
            "success"
        );

        // SAVE DOWNLOAD HISTORY

        saveDownloadHistory(filename, format);

    } catch (error) {
        showStatus(
            downloadMessage,
            error.message || "Download failed. Please try again.",
            "error"
        );

    } finally {
        setButtonLoading(downloadBtn, false);
    }
}


// =============================================
// DOWNLOAD HISTORY SYSTEM
// =============================================

// GET HISTORY

function getDownloadHistory() {
    try {
        return JSON.parse(
            localStorage.getItem(HISTORY_KEY)
        ) || [];

    } catch (error) {
        return [];
    }
}


// SAVE DOWNLOAD

function saveDownloadHistory(filename, format) {
    const history = getDownloadHistory();

    const item = {
        id: Date.now(),
        filename: filename,
        format: format.toUpperCase(),
        date: new Date().toLocaleString()
    };

    history.unshift(item);

    localStorage.setItem(
        HISTORY_KEY,
        JSON.stringify(history.slice(0, 50))
    );

    renderDownloadHistory();
}


// DISPLAY HISTORY

function renderDownloadHistory() {
    const historyList = document.getElementById("historyList");

    if (!historyList) return;

    const history = getDownloadHistory();

    historyList.innerHTML = "";

    if (history.length === 0) {
        historyList.innerHTML = `
            <div class="empty-history">
                <span>📂</span>
                <p>No downloads yet. Your download history will appear here.</p>
            </div>
        `;

        return;
    }

    history.forEach(item => {
        const historyItem = document.createElement("div");
        historyItem.className = "history-item";

        const fileContainer = document.createElement("div");
        fileContainer.className = "history-file";

        const icon = document.createElement("span");
        icon.className = "history-icon";
        icon.textContent = item.format === "MP3" ? "🎵" : "🎬";

        const details = document.createElement("div");
        details.className = "history-details";

        const title = document.createElement("h4");
        title.textContent = item.filename;

        const date = document.createElement("p");
        date.textContent = item.date;

        details.append(title, date);
        fileContainer.append(icon, details);

        const actions = document.createElement("div");

        actions.style.cssText = `
            display: flex;
            align-items: center;
            gap: 10px;
        `;

        const formatBadge = document.createElement("span");
        formatBadge.className = "history-format";
        formatBadge.textContent = item.format;

        // DELETE BUTTON

        const deleteButton = document.createElement("button");

        deleteButton.type = "button";
        deleteButton.textContent = "✕";
        deleteButton.title = "Delete history item";

        deleteButton.setAttribute(
            "aria-label",
            "Delete history item"
        );

        deleteButton.style.cssText = `
            background: #351b2a;
            color: #fca5a5;
            border: 1px solid #713b55;
            border-radius: 8px;
            padding: 7px 11px;
            cursor: pointer;
        `;

        deleteButton.addEventListener("click", () => {
            deleteHistoryItem(item.id);
        });

        actions.append(formatBadge, deleteButton);

        historyItem.append(fileContainer, actions);

        historyList.appendChild(historyItem);
    });
}


// DELETE INDIVIDUAL HISTORY ITEM

function deleteHistoryItem(id) {
    const updatedHistory = getDownloadHistory().filter(
        item => item.id !== id
    );

    localStorage.setItem(
        HISTORY_KEY,
        JSON.stringify(updatedHistory)
    );

    renderDownloadHistory();
}


// CLEAR ALL HISTORY

function clearHistory() {
    if (!confirm("Are you sure you want to clear all download history?")) {
        return;
    }

    localStorage.removeItem(HISTORY_KEY);

    renderDownloadHistory();
}


// =============================================
// DOWNLOAD STATISTICS SYSTEM
// =============================================

function renderDownloadStats() {
    const history = getDownloadHistory();

    const total = history.length;

    const mp4 = history.filter(
        item => item.format === "MP4"
    ).length;

    const mp3 = history.filter(
        item => item.format === "MP3"
    ).length;

    const totalElement = document.getElementById("totalDownloads");
    const mp4Element = document.getElementById("mp4Downloads");
    const mp3Element = document.getElementById("mp3Downloads");

    if (totalElement) totalElement.textContent = total;
    if (mp4Element) mp4Element.textContent = mp4;
    if (mp3Element) mp3Element.textContent = mp3;
}


// UPDATE STATISTICS WHEN HISTORY CHANGES

const originalRenderHistory = renderDownloadHistory;

renderDownloadHistory = function() {
    originalRenderHistory();
    renderDownloadStats();
};


// =============================================
// RESPONSIVE MOBILE NAVBAR
// =============================================

function initializeMobileNavbar() {
    const navbar = document.querySelector(".navbar");
    const navLinks = document.querySelector(".nav-links");

    if (!navbar || !navLinks) return;

    if (document.querySelector(".mobile-menu-btn")) return;

    const menuButton = document.createElement("button");

    menuButton.className = "mobile-menu-btn";
    menuButton.type = "button";
    menuButton.textContent = "☰";

    menuButton.setAttribute("aria-label", "Open navigation menu");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-controls", "vidxNavigation");

    navLinks.id = "vidxNavigation";

    navbar.appendChild(menuButton);

    const mobileNavStyle = document.createElement("style");

    mobileNavStyle.textContent = `

        .mobile-menu-btn {
            display: none;
            background: linear-gradient(135deg, #7c3aed, #6366f1);
            color: white;
            border: none;
            border-radius: 9px;
            padding: 9px 14px;
            font-size: 23px;
            cursor: pointer;
            line-height: 1;
            z-index: 1001;
        }

        @media (max-width: 700px) {

            .navbar {
                position: sticky;
                top: 0;
                z-index: 1000;
            }

            .mobile-menu-btn {
                display: block;
            }

            .nav-links {
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                width: 100%;
                flex-direction: column;
                align-items: stretch;
                gap: 0;
                padding: 10px 20px 18px;
                background: #10172a;
                border: 1px solid rgba(167,139,250,0.2);
                border-top: none;
                border-radius: 0 0 15px 15px;
                box-shadow: 0 15px 30px rgba(0,0,0,0.35);
            }

            .nav-links.active {
                display: flex;
                animation: vidxMenuOpen 0.25s ease;
            }

            .nav-links a {
                display: block;
                padding: 14px 12px;
                border-bottom: 1px solid rgba(255,255,255,0.07);
                color: #f8fafc;
            }

            .nav-links a:last-child {
                border-bottom: none;
            }

            .nav-links a:hover {
                background: rgba(139,92,246,0.12);
                border-radius: 8px;
            }
        }

        @keyframes vidxMenuOpen {
            from {
                opacity: 0;
                transform: translateY(-8px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

    `;

    document.head.appendChild(mobileNavStyle);

    menuButton.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("active");

        menuButton.textContent = isOpen ? "✕" : "☰";

        menuButton.setAttribute(
            "aria-expanded",
            String(isOpen)
        );

        menuButton.setAttribute(
            "aria-label",
            isOpen ? "Close navigation menu" : "Open navigation menu"
        );
    });

    navLinks.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", () => {
            navLinks.classList.remove("active");

            menuButton.textContent = "☰";

            menuButton.setAttribute("aria-expanded", "false");
            menuButton.setAttribute("aria-label", "Open navigation menu");
        });
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 700) {
            navLinks.classList.remove("active");

            menuButton.textContent = "☰";

            menuButton.setAttribute("aria-expanded", "false");
        }
    });
}


// =============================================
// DARK / LIGHT MODE
// =============================================

function initializeTheme() {
    const navbar = document.querySelector(".navbar");

    if (!navbar) return;

    // PREVENT DUPLICATE THEME BUTTON

    if (document.getElementById("themeToggle")) return;

    const themeButton = document.createElement("button");

    themeButton.id = "themeToggle";
    themeButton.className = "theme-toggle";
    themeButton.type = "button";
    themeButton.title = "Toggle theme";
    themeButton.setAttribute("aria-label", "Toggle color theme");

    // LOAD SAVED THEME

    const savedTheme = localStorage.getItem(THEME_KEY) || "dark";

    document.body.setAttribute("data-theme", savedTheme);

    themeButton.textContent =
        savedTheme === "dark" ? "☀️" : "🌙";

    navbar.appendChild(themeButton);

    // TOGGLE THEME

    themeButton.addEventListener("click", () => {

        const currentTheme =
            document.body.getAttribute("data-theme");

        const newTheme =
            currentTheme === "dark" ? "light" : "dark";

        document.body.setAttribute("data-theme", newTheme);

        localStorage.setItem(THEME_KEY, newTheme);

        themeButton.textContent =
            newTheme === "dark" ? "☀️" : "🌙";

    });
}


// =============================================
// INITIALIZE ALL FEATURES
// =============================================

function initializeVidX() {
    renderDownloadHistory();
    renderDownloadStats();
    initializeMobileNavbar();
    initializeTheme();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeVidX);
} else {
    initializeVidX();
}


// =============================================
// VIDX JAVASCRIPT COMPLETE
// =============================================
