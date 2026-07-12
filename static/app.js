const API_BASE = "";

let currentInfo = null;
let pollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  loadDownloads();
});

function getInfo() {
  const url = document.getElementById("url-input").value.trim();
  if (!url) return showError("Please enter a URL");

  const btn = document.getElementById("info-btn");
  btn.disabled = true;
  btn.textContent = "Fetching...";
  hideError();
  document.getElementById("info-display").classList.add("hidden");

  fetch(`${API_BASE}/api/info`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) return showError(data.error);
      currentInfo = { url, ...data };
      showInfo(data);
    })
    .catch((e) => showError("Network error: " + e.message))
    .finally(() => {
      btn.disabled = false;
      btn.textContent = "Get Info";
    });
}

function showInfo(info) {
  document.getElementById("info-display").classList.remove("hidden");
  document.getElementById("video-title").textContent = info.title;

  const thumb = document.getElementById("video-thumbnail");
  if (info.thumbnail) {
    thumb.src = info.thumbnail;
    thumb.classList.remove("hidden");
  } else {
    thumb.classList.add("hidden");
  }

  const duration = document.getElementById("video-duration");
  const mins = Math.floor(info.duration / 60);
  const secs = info.duration % 60;
  duration.textContent = `${mins}m ${secs}s`;

  const select = document.getElementById("format-select");
  select.innerHTML = "";
  if (!info.formats || info.formats.length === 0) {
    select.innerHTML = '<option value="">No formats available</option>';
    return;
  }
  info.formats.forEach((f) => {
    const opt = document.createElement("option");
    opt.value = f.id;
    const size = f.filesize ? ` (${(f.filesize / 1048576).toFixed(1)}MB)` : "";
    const label = `${f.height}p · ${f.ext} · ${f.vcodec}${size}`;
    opt.textContent = label;
    if (f.height >= 1080) opt.style.fontWeight = "bold";
    select.appendChild(opt);
  });
}

function startDownload() {
  if (!currentInfo) return showError("Get video info first");

  const formatId = document.getElementById("format-select").value;
  if (!formatId) return showError("Select a format");

  const customName = document.getElementById("filename-input").value.trim();

  const btn = document.getElementById("download-btn");
  btn.disabled = true;
  btn.textContent = "Starting...";
  hideError();

  fetch(`${API_BASE}/api/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: currentInfo.url,
      format_id: formatId,
      filename: customName || undefined,
      title: currentInfo.title,
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) return showError(data.error);
      showProgress(data.download_id);
    })
    .catch((e) => {
      showError("Download failed: " + e.message);
      btn.disabled = false;
      btn.textContent = "Download";
    });
}

function showProgress(downloadId) {
  document.getElementById("progress-section").classList.remove("hidden");
  const bar = document.getElementById("progress-bar");
  const text = document.getElementById("progress-text");

  pollInterval = setInterval(() => {
    fetch(`${API_BASE}/api/status/${downloadId}`)
      .then((r) => r.json())
      .then((state) => {
        if (state.error) {
          clearInterval(pollInterval);
          showError(state.error);
          enableDownloadBtn();
          return;
        }
        bar.style.width = state.progress + "%";
        bar.textContent = state.progress.toFixed(1) + "%";
        if (state.status === "downloading") {
          text.textContent = `${state.speed || "?"} · ETA: ${state.eta || "?"}s`;
        } else if (state.status === "completed") {
          text.textContent = "Download complete!";
          clearInterval(pollInterval);
          enableDownloadBtn();
          loadDownloads();
          setTimeout(() => {
            document.getElementById("progress-section").classList.add("hidden");
          }, 3000);
        } else if (state.status === "error") {
          text.textContent = "Error: " + state.error;
          clearInterval(pollInterval);
          enableDownloadBtn();
        }
      })
      .catch(() => {});
  }, 1000);
}

function enableDownloadBtn() {
  const btn = document.getElementById("download-btn");
  btn.disabled = false;
  btn.textContent = "Download";
}

function loadDownloads() {
  fetch(`${API_BASE}/api/downloads`)
    .then((r) => r.json())
    .then((data) => {
      const list = document.getElementById("downloads-list");
      list.innerHTML = "";
      if (!data.downloads || data.downloads.length === 0) {
        list.innerHTML = '<li class="empty">No downloads yet</li>';
        return;
      }
      data.downloads.reverse().forEach((d) => {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = `${API_BASE}/downloads/${encodeURIComponent(d.filename)}`;
        link.textContent = d.title || d.filename;
        link.download = d.filename;
        const size = d.total_bytes
          ? ` (${(d.total_bytes / 1048576).toFixed(1)} MB)`
          : "";
        const span = document.createElement("span");
        span.textContent = size;
        li.appendChild(link);
        li.appendChild(span);
        list.appendChild(li);
      });
    })
    .catch(() => {});
}

function showError(msg) {
  const el = document.getElementById("error-message");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideError() {
  document.getElementById("error-message").classList.add("hidden");
}

function handleKeyPress(e) {
  if (e.key === "Enter") getInfo();
}
