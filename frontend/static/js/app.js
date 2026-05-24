/**
 * Audiobook Generator — PDF intake, chunk preview, sequential TTS generation.
 */

(function () {
  "use strict";

  const STORAGE_SKIP_PREVIEW = "aminvoice_skip_pdf_preview";

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

  let currentIntake = null;
  let isEditing = false;
  let pollTimer = null;

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

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function formatStatusLabel(data) {
    if (data.status_label && data.status_label !== "—") {
      return data.status_label;
    }
    if (data.status === "waiting_quota") {
      const wait = data.wait_seconds || 45;
      return "Waiting for Gemini quota reset (~" + wait + "s)";
    }
    if (data.status === "merging") return "Merging final audio";
    if (data.status === "generating") return "Generating audiobook";
    if (data.status === "completed") return "Audiobook ready";
    if (data.status === "failed") return "Generation failed";
    if (data.status === "cancelled" || data.status === "cancelling") {
      return "Generation cancelled";
    }
    return data.status || "—";
  }

  function updateProgressUI(data) {
    if (progressStatus) {
      progressStatus.textContent = formatStatusLabel(data);
      progressStatus.classList.toggle("text-amber-300", data.status === "waiting_quota");
      progressStatus.classList.toggle("text-accent", data.status === "generating" || data.status === "merging");
      progressStatus.classList.toggle("text-emerald-400", data.status === "completed");
      progressStatus.classList.toggle("text-red-400", data.status === "failed");
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
      if (typeof data.progress_percent === "number" && data.total_chunks > 0) {
        progressPercent.textContent = Math.round(data.progress_percent) + "%";
      } else {
        progressPercent.textContent = "—";
      }
    }
    if (progressChunkSize) {
      progressChunkSize.textContent =
        data.current_chunk_size > 0 ? data.current_chunk_size + " chars" : "—";
    }
    if (progressChunkPreview) {
      progressChunkPreview.textContent = data.current_chunk_preview || "—";
    }
    if (progressEta) progressEta.textContent = data.eta || "—";
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
    if (!currentIntake) return;
    const response = await fetch(
      "/api/v1/pdf/" + currentIntake.intake_id + "/generation/status"
    );
    if (response.status === 404) return;
    const data = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) return;

    updateProgressUI(data);

    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = setInterval(pollGenerationStatus, pollIntervalMs(data));
    }

    const terminal = ["completed", "failed", "cancelled"];
    if (terminal.indexOf(data.status) >= 0) {
      stopPolling();
      if (btnCancelGeneration) btnCancelGeneration.classList.add("hidden");
    }

    if (data.status === "completed") {
      if (downloadAudiobook) {
        downloadAudiobook.classList.remove("hidden");
        downloadAudiobook.href =
          "/api/v1/pdf/" + currentIntake.intake_id + "/audiobook/download";
      }
      showGenerationMessage("Audiobook ready — download below.");
      return;
    }

    if (data.status === "failed") {
      showGenerationMessage(data.error || "Generation failed.", true);
      return;
    }

    if (data.status === "cancelled") {
      showGenerationMessage("Generation cancelled.");
    }
  }

  function pollIntervalMs(data) {
    if (!data) return 2000;
    if (data.status === "waiting_quota" || data.status === "generating") return 1000;
    return 2000;
  }

  function schedulePoll() {
    stopPolling();
    pollTimer = setInterval(pollGenerationStatus, 1500);
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

    if (progressStatus) progressStatus.textContent = "Starting…";
    if (progressProject) progressProject.textContent = currentIntake.filename;
    if (btnCancelGeneration) btnCancelGeneration.classList.remove("hidden");
    if (downloadAudiobook) downloadAudiobook.classList.add("hidden");

    const response = await fetch(
      "/api/v1/pdf/" + currentIntake.intake_id + "/continue",
      { method: "POST" }
    );
    const payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      showActionMessage(formatApiError(payload, "Continue failed."), true);
      if (btnCancelGeneration) btnCancelGeneration.classList.add("hidden");
      return;
    }

    updateProgressUI({
      status: "generating",
      status_label: "Starting generation…",
      current_chunk: 0,
      total_chunks: payload.total_chunks || 0,
      current_token_index: 0,
      total_tokens: 0,
      current_chunk_size: 0,
      current_chunk_preview: "",
      progress_percent: 0,
      eta: "estimating...",
    });

    showActionMessage("Generating audiobook (" + payload.total_chunks + " chunks)…");
    showGenerationMessage("Sequential TTS in progress — status updates every second.");

    schedulePoll();
    pollGenerationStatus();
  }

  async function cancelGeneration() {
    if (!currentIntake) return;
    await fetch("/api/v1/pdf/" + currentIntake.intake_id + "/generation/cancel", {
      method: "POST",
    });
    showGenerationMessage("Cancelling generation…");
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
  }

  checkTokenConfiguration();
})();
