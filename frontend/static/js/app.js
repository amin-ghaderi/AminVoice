/**
 * Audiobook Generator — PDF intake, chunk preview, sequential TTS generation.
 */

(function () {
  "use strict";

  const STORAGE_SKIP_PREVIEW = "aminvoice_skip_pdf_preview";

  const CHUNK_QUALITY_MAP = {
    ultra: 600,
    high: 800,
    balanced: 1000,
    fast: 1150,
    max: 1300,
  };

  const chunkQualitySelect = document.getElementById("chunk-quality");

  function getValidationMaxChars() {
    const key = chunkQualitySelect ? chunkQualitySelect.value : "balanced";
    return CHUNK_QUALITY_MAP[key] != null ? CHUNK_QUALITY_MAP[key] : CHUNK_QUALITY_MAP.balanced;
  }

  function formatApiError(payload, fallback) {
    const detail = payload && payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (item) {
        return item.msg || JSON.stringify(item);
      }).join("; ");
    }
    return fallback;
  }

  const pdfInput = document.getElementById("pdf-upload");
  const uploadSection = document.getElementById("upload-section");
  const previewSection = document.getElementById("preview-section");
  const uploadError = document.getElementById("upload-error");
  const uploadLoading = document.getElementById("upload-loading");
  const uploadHint = document.getElementById("upload-hint");
  const previewFilename = document.getElementById("preview-filename");
  const previewPageCount = document.getElementById("preview-page-count");
  const previewReadonly = document.getElementById("preview-readonly");
  const previewEditor = document.getElementById("preview-editor");
  const skipPreviewNext = document.getElementById("skip-preview-next");
  const btnContinue = document.getElementById("btn-continue");
  const btnEdit = document.getElementById("btn-edit");
  const btnSaveEdit = document.getElementById("btn-save-edit");
  const btnCancel = document.getElementById("btn-cancel");
  const previewActionMsg = document.getElementById("preview-action-msg");
  const repairBadge = document.getElementById("repair-badge");
  const repairFixCount = document.getElementById("repair-fix-count");
  const generationProgressSection = document.getElementById("generation-progress-section");
  const progressActivityText = document.getElementById("progress-activity-text");
  const progressActivityDots = document.getElementById("progress-activity-dots");
  const progressActivity = document.getElementById("progress-activity");
  const progressPulseDot = document.getElementById("progress-pulse-dot");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const progressLastUpdated = document.getElementById("progress-last-updated");
  const progressStatus = document.getElementById("progress-status");
  const progressChunk = document.getElementById("progress-chunk");
  const progressProject = document.getElementById("progress-project");
  const progressToken = document.getElementById("progress-token");
  const progressEta = document.getElementById("progress-eta");
  const progressPercent = document.getElementById("progress-percent");
  const progressChunkSize = document.getElementById("progress-chunk-size");
  const progressChunkPreview = document.getElementById("progress-chunk-preview");
  const btnCancelGeneration = document.getElementById("btn-cancel-generation");
  const downloadAudiobook = document.getElementById("download-audiobook");
  const generationMsg = document.getElementById("generation-msg");
  const btnPreviewChunks = document.getElementById("btn-preview-chunks");
  const chunkModal = document.getElementById("chunk-modal");
  const chunkModalBackdrop = document.getElementById("chunk-modal-backdrop");
  const chunkModalClose = document.getElementById("chunk-modal-close");
  const chunkModalList = document.getElementById("chunk-modal-list");
  const chunkStatTotal = document.getElementById("chunk-stat-total");
  const chunkStatAvg = document.getElementById("chunk-stat-avg");
  const chunkStatMin = document.getElementById("chunk-stat-min");
  const chunkStatMax = document.getElementById("chunk-stat-max");
  const tokenWarning = document.getElementById("token-warning");
  const tokenPoolMonitorSection = document.getElementById("token-pool-monitor-section");
  const tokenNowUsingName = document.getElementById("token-now-using-name");
  const tokenPoolList = document.getElementById("token-pool-list");
  const tokenSwitchHistory = document.getElementById("token-switch-history");
  const tokenMonitorUpdated = document.getElementById("token-monitor-updated");
  const audioQualitySection = document.getElementById("audio-quality-section");
  const qualityLabelBadge = document.getElementById("quality-label-badge");
  const qualitySilence = document.getElementById("quality-silence");
  const qualityDiscontinuities = document.getElementById("quality-discontinuities");
  const qualityVariance = document.getElementById("quality-variance");
  const qualityVariation = document.getElementById("quality-variation");
  const qualityChunksMeta = document.getElementById("quality-chunks-meta");
  const sceneEnable = document.getElementById("scene-enable");
  const sceneFields = document.getElementById("scene-fields");
  const sceneInput = document.getElementById("scene-input");
  const sceneStyle = document.getElementById("scene-style");
  const sceneTone = document.getElementById("scene-tone");

  let currentIntake = null;
  let isEditing = false;
  let pollTimer = null;
  let heartbeatTimer = null;
  let tokenMonitorTimer = null;
  let generationActive = false;
  let lastPollSuccessAt = 0;
  let lastTokenMonitorAt = 0;
  let lastGoodStatus = null;
  let rotateIndex = 0;
  let pollInFlight = false;
  let tokenMonitorInFlight = false;

  const ROTATING_ACTIVITY = [
    "Processing audio…",
    "Enhancing narration…",
    "Preparing next segment…",
    "Optimizing voice engine…",
  ];

  const TERMINAL_STATUSES = ["completed", "failed", "cancelled"];
  const ACTIVE_STATUSES = ["generating", "waiting_quota", "merging", "cancelling"];

  function shouldSkipPreview() {
    return localStorage.getItem(STORAGE_SKIP_PREVIEW) === "true";
  }

  function setSkipPreview(value) {
    localStorage.setItem(STORAGE_SKIP_PREVIEW, value ? "true" : "false");
  }

  if (skipPreviewNext) {
    skipPreviewNext.checked = shouldSkipPreview();
    skipPreviewNext.addEventListener("change", function () {
      setSkipPreview(skipPreviewNext.checked);
    });
  }

  function showError(message) {
    if (!uploadError) return;
    uploadError.textContent = message;
    uploadError.classList.remove("hidden");
  }

  function clearError() {
    if (!uploadError) return;
    uploadError.textContent = "";
    uploadError.classList.add("hidden");
  }

  function setLoading(active) {
    if (uploadLoading) uploadLoading.classList.toggle("hidden", !active);
    if (pdfInput) pdfInput.disabled = active;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatPersianBody(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return "";

    return trimmed
      .split(/\n\s*\n/)
      .map(function (block) {
        const lines = block
          .split("\n")
          .map(function (line) {
            return escapeHtml(line.trim());
          })
          .filter(Boolean);
        if (!lines.length) return "";
        return '<p class="persian-paragraph">' + lines.join("<br>") + "</p>";
      })
      .filter(Boolean)
      .join("");
  }

  function renderPageSections(pages) {
    return pages
      .map(function (page) {
        const body = formatPersianBody(page.text);
        const empty = !body;
        return (
          '<article class="mb-8 border-b border-slate-700/80 pb-6 last:mb-0 last:border-0 last:pb-0">' +
          '<h3 class="preview-page-label mb-3 text-xs font-semibold uppercase text-accent">Page ' +
          page.page_number +
          "</h3>" +
          (empty
            ? '<p class="text-sm italic text-slate-500" dir="ltr" style="text-align:left">(no text on this page)</p>'
            : '<div class="preview-page-body">' + body + "</div>") +
          "</article>"
        );
      })
      .join("");
  }

  function showPreview(data) {
    currentIntake = data;
    if (previewFilename) previewFilename.textContent = data.filename;
    if (previewPageCount) previewPageCount.textContent = String(data.page_count);
    if (previewReadonly) previewReadonly.innerHTML = renderPageSections(data.pages);
    if (previewEditor) previewEditor.value = data.full_text;
    if (previewSection) previewSection.classList.remove("hidden");
    if (previewActionMsg) previewActionMsg.classList.add("hidden");
    if (repairBadge && repairFixCount) {
      const count = data.repair_fix_count || 0;
      repairFixCount.textContent = String(count);
      repairBadge.classList.toggle("hidden", count === 0);
    }
    exitEditMode();
  }

  function hidePreview() {
    currentIntake = null;
    if (previewSection) previewSection.classList.add("hidden");
    if (previewReadonly) previewReadonly.innerHTML = "";
    if (previewEditor) previewEditor.value = "";
    if (uploadHint) uploadHint.textContent = "Click to select a Persian PDF";
    if (pdfInput) pdfInput.value = "";
    if (repairBadge) repairBadge.classList.add("hidden");
    exitEditMode();
  }

  function enterEditMode() {
    isEditing = true;
    if (previewReadonly) previewReadonly.classList.add("hidden");
    if (previewEditor) previewEditor.classList.remove("hidden");
    if (btnEdit) btnEdit.classList.add("hidden");
    if (btnSaveEdit) btnSaveEdit.classList.remove("hidden");
  }

  function exitEditMode() {
    isEditing = false;
    if (previewReadonly) previewReadonly.classList.remove("hidden");
    if (previewEditor) previewEditor.classList.add("hidden");
    if (btnEdit) btnEdit.classList.remove("hidden");
    if (btnSaveEdit) btnSaveEdit.classList.add("hidden");
  }

  async function uploadPdf(file) {
    clearError();
    setLoading(true);
    if (uploadHint) uploadHint.textContent = file.name;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/v1/pdf/upload", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(function () {
        return {};
      });

      if (!response.ok) {
        throw new Error(formatApiError(payload, "Upload failed."));
      }

      if (shouldSkipPreview()) {
        currentIntake = payload;
        await continueToGeneration();
        showActionMessage("Text extracted. Preview skipped (preference saved).");
      } else {
        showPreview(payload);
      }
    } catch (err) {
      showError(err.message || "Could not process PDF.");
      if (uploadHint) uploadHint.textContent = "Click to select a Persian PDF";
    } finally {
      setLoading(false);
    }
  }

  async function saveEdits() {
    if (!currentIntake) return;
    const text = previewEditor ? previewEditor.value : "";
    const response = await fetch("/api/v1/pdf/" + currentIntake.intake_id + "/text", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_text: text }),
    });
    const payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      showActionMessage(formatApiError(payload, "Could not save edits."), true);
      return;
    }
    showPreview(payload);
    showActionMessage("Edits saved.");
  }

  function clearPollTimers() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  }

  function clearTokenMonitorTimer() {
    if (tokenMonitorTimer) {
      clearInterval(tokenMonitorTimer);
      tokenMonitorTimer = null;
    }
  }

  function updateTokenMonitorTimestamp() {
    if (!tokenMonitorUpdated) return;
    if (!lastTokenMonitorAt) {
      tokenMonitorUpdated.textContent = "—";
      return;
    }
    const seconds = Math.max(0, Math.floor((Date.now() - lastTokenMonitorAt) / 1000));
    tokenMonitorUpdated.textContent =
      seconds <= 1 ? "Updated just now" : "Updated " + seconds + "s ago";
  }

  function renderTokenPoolMonitor(data) {
    if (!data) return;

    const isLive = Boolean(data.generation_active || data.active);
    if (tokenPoolMonitorSection) {
      tokenPoolMonitorSection.classList.toggle("is-live", isLive);
    }

    const using = data.now_using || data.active_token_name || data.current_token_name || "—";
    if (tokenNowUsingName) tokenNowUsingName.textContent = using;

    if (tokenPoolList) {
      const items = data.tokens || [];
      if (!items.length) {
        tokenPoolList.innerHTML =
          '<p class="text-sm text-slate-500">No enabled tokens. <a href="/settings" class="text-accent hover:underline">Add keys</a>.</p>';
      } else {
        tokenPoolList.innerHTML = items
          .map(function (item) {
            const status = (item.status || "idle").toLowerCase();
            const rowClass =
              "token-pool-item" +
              (status === "active" ? " is-active" : "") +
              (status === "waiting" ? " is-waiting" : "") +
              (status === "failed" ? " is-failed" : "");
            const badgeClass = "token-status-badge " + status;
            const label =
              status === "active"
                ? "Active"
                : status === "waiting"
                  ? "Waiting"
                  : status === "failed"
                    ? "Failed"
                    : "Idle";
            return (
              '<div class="' +
              rowClass +
              '">' +
              '<div><span class="text-sm font-medium text-slate-200">' +
              escapeHtml(item.name) +
              '</span><span class="ml-2 text-xs text-slate-500">#' +
              item.priority +
              "</span></div>" +
              '<span class="' +
              badgeClass +
              '">' +
              label +
              "</span></div>"
            );
          })
          .join("");
      }
    }

    if (tokenSwitchHistory) {
      const switches = data.switch_history || [];
      if (!switches.length) {
        tokenSwitchHistory.innerHTML =
          '<li class="text-slate-600">No switches yet this session.</li>';
      } else {
        tokenSwitchHistory.innerHTML = switches
          .slice()
          .reverse()
          .map(function (ev) {
            return (
              "<li>Chunk " +
              ev.chunk_id +
              ": " +
              escapeHtml(ev.from_token) +
              " → " +
              escapeHtml(ev.to_token) +
              " (" +
              escapeHtml(ev.reason) +
              ")</li>"
            );
          })
          .join("");
      }
    }
  }

  async function pollTokenMonitor() {
    if (tokenMonitorInFlight) return;
    tokenMonitorInFlight = true;
    try {
      const response = await fetch("/api/v1/tokens/runtime-status");
      const data = await response.json().catch(function () {
        return null;
      });
      if (!response.ok || !data) return;
      lastTokenMonitorAt = Date.now();
      renderTokenPoolMonitor(data);
      updateTokenMonitorTimestamp();
    } catch (_err) {
      /* keep last render */
    } finally {
      tokenMonitorInFlight = false;
    }
  }

  function startTokenMonitorPolling() {
    clearTokenMonitorTimer();
    pollTokenMonitor();
    tokenMonitorTimer = setInterval(pollTokenMonitor, 1500);
  }

  function renderAudioQualityReport(data) {
    if (!data) return;
    if (audioQualitySection) audioQualitySection.classList.remove("hidden");

    if (qualitySilence) {
      qualitySilence.textContent = (data.avg_chunk_silence_ratio * 100).toFixed(1) + "%";
    }
    if (qualityDiscontinuities) {
      qualityDiscontinuities.textContent = String(data.discontinuities_count);
    }
    if (qualityVariance) {
      qualityVariance.textContent = data.loudness_variance.toFixed(1) + " dB²";
    }
    if (qualityVariation) {
      qualityVariation.textContent = data.chunk_variation_score.toFixed(1) + " / 100";
    }
    if (qualityChunksMeta) {
      qualityChunksMeta.textContent =
        "Analyzed " + data.chunk_count + " chunk WAV files for this audiobook.";
    }
    if (qualityLabelBadge) {
      const label = (data.quality_label || "unknown").replace("_", " ");
      qualityLabelBadge.textContent = label;
      qualityLabelBadge.className =
        "rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide quality-badge-" +
        (data.quality_label || "fair");
    }
  }

  function hideAudioQualityReport() {
    if (audioQualitySection) audioQualitySection.classList.add("hidden");
  }

  async function fetchAudioQualityReport() {
    if (!currentIntake) return;
    try {
      const response = await fetch(
        "/api/v1/pdf/" + currentIntake.intake_id + "/audio-quality"
      );
      if (response.status === 404) {
        hideAudioQualityReport();
        return;
      }
      const data = await response.json().catch(function () {
        return null;
      });
      if (response.ok && data) {
        renderAudioQualityReport(data);
      }
    } catch (_err) {
      hideAudioQualityReport();
    }
  }

  function stopPolling() {
    clearPollTimers();
    generationActive = false;
    pollInFlight = false;
    if (generationProgressSection) {
      generationProgressSection.classList.remove("gen-panel-active");
    }
  }

  function startGenerationUX() {
    generationActive = true;
    rotateIndex = 0;
    lastPollSuccessAt = Date.now();
    lastGoodStatus = null;
    if (generationProgressSection) {
      generationProgressSection.classList.add("gen-panel-active");
    }
    clearPollTimers();
    pollTimer = setInterval(pollGenerationStatus, 1200);
    heartbeatTimer = setInterval(tickHeartbeat, 1000);
    startTokenMonitorPolling();
    tickHeartbeat();
  }

  function mapSemanticActivity(data, rotation) {
    const status = data.status || "";
    if (status === "merging") return "Finalizing audiobook…";
    if (status === "completed") return "Your audiobook is ready";
    if (status === "failed") return "We could not finish this audiobook";
    if (status === "cancelled" || status === "cancelling") {
      return "Stopping after the current segment…";
    }
    if (status === "waiting_quota") {
      return ROTATING_ACTIVITY[rotation % ROTATING_ACTIVITY.length];
    }
    if (status === "generating") {
      if (!data.current_chunk) return "Preparing audio segments…";
      if (rotation % 5 === 0) return "Generating narration…";
      if (rotation % 5 === 1) return "Optimizing voice output…";
      return ROTATING_ACTIVITY[rotation % ROTATING_ACTIVITY.length];
    }
    return "Preparing audio segments…";
  }

  function formatEtaFriendly(eta) {
    if (!eta || eta === "—") return "Calculating…";
    if (eta === "estimating...") return "Calculating time remaining…";
    if (eta === "merging...") return "Almost done…";
    if (eta === "done") return "Complete";
    if (eta.indexOf("~") === 0) {
      return "About " + eta.slice(1).trim() + " left";
    }
    return eta;
  }

  function computeProgressPercent(data) {
    if (typeof data.progress_percent === "number" && data.progress_percent > 0) {
      return Math.min(100, Math.round(data.progress_percent));
    }
    if (data.total_chunks > 0 && data.current_chunk > 0) {
      return Math.min(100, Math.round((data.current_chunk / data.total_chunks) * 100));
    }
    return 0;
  }

  function setPulseState(status) {
    if (!progressPulseDot) return;
    progressPulseDot.classList.remove("is-idle", "is-waiting", "is-done");
    if (status === "completed") {
      progressPulseDot.classList.add("is-done");
      return;
    }
    if (status === "failed" || status === "cancelled") {
      progressPulseDot.classList.add("is-idle");
      return;
    }
    if (status === "waiting_quota") {
      progressPulseDot.classList.add("is-waiting");
      return;
    }
    if (ACTIVE_STATUSES.indexOf(status) >= 0) {
      return;
    }
    progressPulseDot.classList.add("is-idle");
  }

  function updateActivityPresentation(data, rotation) {
    const label = mapSemanticActivity(data, rotation);
    const showDots = ACTIVE_STATUSES.indexOf(data.status) >= 0;

    if (progressActivityText) progressActivityText.textContent = label;
    if (progressActivityDots) {
      progressActivityDots.classList.toggle("hidden", !showDots);
      if (showDots) {
        progressActivityDots.textContent = ".".repeat((rotation % 3) + 1);
      } else {
        progressActivityDots.textContent = "";
      }
    }
    if (progressActivity) {
      progressActivity.classList.toggle("is-waiting", data.status === "waiting_quota");
      progressActivity.classList.toggle("is-done", data.status === "completed");
    }
    setPulseState(data.status);
    if (progressStatus) progressStatus.textContent = label;
  }

  function updateProgressUI(data) {
    const percent = computeProgressPercent(data);
    updateActivityPresentation(data, rotateIndex);

    if (progressBarFill) {
      progressBarFill.style.width = percent + "%";
      progressBarFill.classList.toggle("is-complete", data.status === "completed");
      const track = progressBarFill.parentElement;
      if (track) {
        track.setAttribute("aria-valuenow", String(percent));
      }
    }

    if (progressChunk) {
      progressChunk.textContent =
        data.total_chunks > 0
          ? data.current_chunk + " / " + data.total_chunks
          : "—";
    }
    if (progressProject && currentIntake) {
      progressProject.textContent = currentIntake.filename;
    }
    if (progressToken) {
      progressToken.textContent =
        data.total_tokens > 0
          ? data.current_token_index + " / " + data.total_tokens
          : "—";
    }
    if (progressPercent) {
      progressPercent.textContent = percent > 0 ? percent + "%" : "—";
    }
    if (progressChunkSize) {
      progressChunkSize.textContent =
        data.current_chunk_size > 0 ? data.current_chunk_size + " chars" : "—";
    }
    if (progressChunkPreview) {
      progressChunkPreview.textContent = data.current_chunk_preview || "—";
    }
    if (progressEta) {
      progressEta.textContent = formatEtaFriendly(data.eta);
    }
  }

  function updateLastUpdatedLabel() {
    if (!progressLastUpdated) return;
    if (!generationActive) {
      progressLastUpdated.textContent = "Last updated: —";
      progressLastUpdated.classList.remove("is-stale");
      return;
    }

    if (!lastPollSuccessAt) {
      progressLastUpdated.textContent = "Syncing with server…";
      progressLastUpdated.classList.add("is-stale");
      return;
    }

    const seconds = Math.max(0, Math.floor((Date.now() - lastPollSuccessAt) / 1000));
    if (seconds > 10) {
      progressLastUpdated.textContent = "Syncing with server…";
      progressLastUpdated.classList.add("is-stale");
      return;
    }

    progressLastUpdated.textContent =
      seconds <= 1 ? "Last updated: just now" : "Last updated: " + seconds + "s ago";
    progressLastUpdated.classList.remove("is-stale");
  }

  function tickHeartbeat() {
    rotateIndex += 1;
    updateTokenMonitorTimestamp();
    if (!generationActive) return;
    updateLastUpdatedLabel();
    if (lastGoodStatus) {
      updateActivityPresentation(lastGoodStatus, rotateIndex);
    } else {
      updateActivityPresentation(
        { status: "generating", current_chunk: 0, total_chunks: 0 },
        rotateIndex
      );
    }
  }

  function showGenerationMessage(msg, isError) {
    if (!generationMsg) return;
    generationMsg.textContent = msg;
    generationMsg.classList.remove("hidden", "text-red-400", "text-slate-400", "text-emerald-400");
    generationMsg.classList.add(
      isError ? "text-red-400" : msg.indexOf("complete") >= 0 ? "text-emerald-400" : "text-slate-400"
    );
  }

  async function pollGenerationStatus() {
    if (!currentIntake || !generationActive) return;
    if (pollInFlight) return;

    pollInFlight = true;
    try {
      const response = await fetch(
        "/api/v1/pdf/" + currentIntake.intake_id + "/generation/status"
      );

      if (response.status === 404) {
        updateLastUpdatedLabel();
        return;
      }

      const data = await response.json().catch(function () {
        return null;
      });

      if (!response.ok || !data) {
        updateLastUpdatedLabel();
        return;
      }

      lastPollSuccessAt = Date.now();
      lastGoodStatus = data;
      updateProgressUI(data);
      pollTokenMonitor();

      if (TERMINAL_STATUSES.indexOf(data.status) >= 0) {
        clearPollTimers();
        generationActive = false;
        if (btnCancelGeneration) btnCancelGeneration.classList.add("hidden");
        if (generationProgressSection) {
          generationProgressSection.classList.remove("gen-panel-active");
        }
      }

      if (data.status === "completed") {
        if (downloadAudiobook) {
          downloadAudiobook.classList.remove("hidden");
          downloadAudiobook.href =
            "/api/v1/pdf/" + currentIntake.intake_id + "/audiobook/download";
        }
        showGenerationMessage("Your audiobook is ready — download below.");
        fetchAudioQualityReport();
        return;
      }

      if (data.status === "failed") {
        showGenerationMessage(
          "Generation stopped before completion. You can try again from the dashboard.",
          true
        );
        return;
      }

      if (data.status === "cancelled") {
        showGenerationMessage("Generation was cancelled.");
      }
    } catch (_err) {
      updateLastUpdatedLabel();
    } finally {
      pollInFlight = false;
    }
  }

  function openChunkModal() {
    if (chunkModal) {
      chunkModal.classList.remove("hidden");
      chunkModal.setAttribute("aria-hidden", "false");
    }
  }

  function closeChunkModal() {
    if (chunkModal) {
      chunkModal.classList.add("hidden");
      chunkModal.setAttribute("aria-hidden", "true");
    }
  }

  function renderChunkPreview(data) {
    if (chunkStatTotal) chunkStatTotal.textContent = String(data.total_chunks);
    if (chunkStatAvg) chunkStatAvg.textContent = data.avg_chars + " chars";
    if (chunkStatMin) chunkStatMin.textContent = data.min_chars + " chars";
    if (chunkStatMax) chunkStatMax.textContent = data.max_chars + " chars";

    if (!chunkModalList) return;
    chunkModalList.innerHTML = (data.chunks || [])
      .map(function (chunk) {
        let badge = "";
        if (chunk.warning === "Too small") {
          badge =
            '<span class="chunk-badge-warn small">Too small</span>';
        } else if (chunk.warning === "Too large") {
          badge =
            '<span class="chunk-badge-warn large">Too large</span>';
        }
        return (
          '<article class="chunk-card">' +
          '<div class="chunk-card-header">' +
          '<span class="text-sm font-semibold text-accent">Chunk #' +
          chunk.index +
          "</span>" +
          '<span class="text-xs text-slate-500">(' +
          chunk.char_count +
          " chars)</span>" +
          badge +
          "</div>" +
          '<div class="chunk-card-body">' +
          escapeHtml(chunk.full_text) +
          "</div>" +
          "</article>"
        );
      })
      .join("");
  }

  async function previewChunks() {
    if (!currentIntake) return;

    if (isEditing && previewEditor) {
      await saveEdits();
    }

    if (btnPreviewChunks) {
      btnPreviewChunks.disabled = true;
      btnPreviewChunks.textContent = "Loading chunks…";
    }

    try {
      const response = await fetch(
        "/api/v1/pdf/" + currentIntake.intake_id + "/chunk-preview",
        { method: "POST" }
      );
      const data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        throw new Error(formatApiError(data, "Chunk preview failed."));
      }
      renderChunkPreview(data);
      openChunkModal();
      showActionMessage("Chunk preview ready (" + data.total_chunks + " chunks).");
    } catch (err) {
      showActionMessage(err.message || "Chunk preview failed.", true);
    } finally {
      if (btnPreviewChunks) {
        btnPreviewChunks.disabled = false;
        btnPreviewChunks.textContent = "Preview chunks";
      }
    }
  }

  function syncSceneFieldsState() {
    const enabled = Boolean(sceneEnable && sceneEnable.checked);
    if (sceneFields) {
      sceneFields.classList.toggle("opacity-60", !enabled);
    }
    [sceneInput, sceneStyle, sceneTone].forEach(function (el) {
      if (el) el.disabled = !enabled;
    });
  }

  function buildContinueFetchOptions() {
    const body = {
      validation_max_chars: getValidationMaxChars(),
    };
    if (sceneEnable && sceneEnable.checked) {
      const sceneText = sceneInput && sceneInput.value.trim();
      body.use_scene = true;
      body.scene = sceneText || null;
      body.style = sceneStyle ? sceneStyle.value : null;
      body.tone = sceneTone ? sceneTone.value : null;
    }
    return {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
  }

  async function continueToGeneration() {
    if (!currentIntake) return;

    const tokenCheck = await fetch("/api/v1/tokens");
    const tokenData = await tokenCheck.json().catch(function () {
      return {};
    });
    if (tokenCheck.ok && !tokenData.configured) {
      showActionMessage("Add at least one Gemini API token in Settings before generating.", true);
      if (tokenWarning) tokenWarning.classList.remove("hidden");
      return;
    }

    if (isEditing && previewEditor) {
      await saveEdits();
    }

    if (progressProject) progressProject.textContent = currentIntake.filename;
    if (btnCancelGeneration) btnCancelGeneration.classList.remove("hidden");
    if (downloadAudiobook) downloadAudiobook.classList.add("hidden");
    hideAudioQualityReport();

    startGenerationUX();
    updateProgressUI({
      status: "generating",
      current_chunk: 0,
      total_chunks: 0,
      progress_percent: 0,
      eta: "estimating...",
    });

    const response = await fetch(
      "/api/v1/pdf/" + currentIntake.intake_id + "/continue",
      buildContinueFetchOptions()
    );
    const payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      stopPolling();
      showActionMessage(formatApiError(payload, "Continue failed."), true);
      if (btnCancelGeneration) btnCancelGeneration.classList.add("hidden");
      return;
    }

    lastGoodStatus = {
      status: "generating",
      current_chunk: 0,
      total_chunks: payload.total_chunks || 0,
      progress_percent: 0,
      eta: "estimating...",
    };
    updateProgressUI(lastGoodStatus);

    showActionMessage(
      "Creating your audiobook (" + (payload.total_chunks || "?") + " segments)…"
    );
    showGenerationMessage("Generation in progress — sit back while we narrate your book.");

    pollGenerationStatus();
  }

  async function cancelGeneration() {
    if (!currentIntake) return;
    await fetch("/api/v1/pdf/" + currentIntake.intake_id + "/generation/cancel", {
      method: "POST",
    });
    generationActive = true;
    updateActivityPresentation(
      { status: "cancelling", current_chunk: lastGoodStatus ? lastGoodStatus.current_chunk : 0 },
      rotateIndex
    );
    showGenerationMessage("Stopping after the current segment…");
    pollGenerationStatus();
  }

  function showActionMessage(msg, isError) {
    if (!previewActionMsg) return;
    previewActionMsg.textContent = msg;
    previewActionMsg.classList.remove("hidden", "text-red-400", "text-slate-400");
    previewActionMsg.classList.add(isError ? "text-red-400" : "text-slate-400");
  }

  async function cancelIntake() {
    if (currentIntake) {
      await fetch("/api/v1/pdf/" + currentIntake.intake_id, { method: "DELETE" });
    }
    hidePreview();
    clearError();
  }

  if (pdfInput) {
    pdfInput.addEventListener("change", function () {
      const file = pdfInput.files && pdfInput.files[0];
      if (file) uploadPdf(file);
    });
  }

  if (btnEdit) {
    btnEdit.addEventListener("click", enterEditMode);
  }

  if (btnSaveEdit) {
    btnSaveEdit.addEventListener("click", saveEdits);
  }

  if (sceneEnable) {
    sceneEnable.addEventListener("change", syncSceneFieldsState);
    syncSceneFieldsState();
  }

  if (btnContinue) {
    btnContinue.addEventListener("click", continueToGeneration);
  }

  if (btnPreviewChunks) {
    btnPreviewChunks.addEventListener("click", previewChunks);
  }

  if (chunkModalClose) {
    chunkModalClose.addEventListener("click", closeChunkModal);
  }
  if (chunkModalBackdrop) {
    chunkModalBackdrop.addEventListener("click", closeChunkModal);
  }

  if (btnCancel) {
    btnCancel.addEventListener("click", cancelIntake);
  }

  if (btnCancelGeneration) {
    btnCancelGeneration.addEventListener("click", cancelGeneration);
  }

  const btnStart = document.getElementById("btn-start");
  if (btnStart) {
    btnStart.addEventListener("click", function () {
      if (currentIntake) continueToGeneration();
    });
  }

  async function checkTokenConfiguration() {
    try {
      const response = await fetch("/api/v1/tokens");
      const data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) return;
      if (tokenWarning) {
        tokenWarning.classList.toggle("hidden", Boolean(data.configured));
      }
    } catch (_err) {
      /* ignore */
    }
    pollTokenMonitor();
    if (!tokenMonitorTimer) {
      tokenMonitorTimer = setInterval(function () {
        pollTokenMonitor();
        updateTokenMonitorTimestamp();
      }, 2000);
    }
  }

  checkTokenConfiguration();
})();
