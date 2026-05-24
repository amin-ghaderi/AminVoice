/**
 * Audiobook Generator — Phase 1: PDF upload & text preview.
 * TODO: chunking, TTS generation, retry system (wired via /continue placeholder).
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

  let currentIntake = null;
  let isEditing = false;

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

  function renderPageSections(pages) {
    return pages
      .map(function (page) {
        const body = escapeHtml(page.text || "").replace(/\n/g, "<br>");
        const empty = !(page.text || "").trim();
        return (
          '<article class="mb-8 border-b border-slate-700/80 pb-6 last:mb-0 last:border-0 last:pb-0">' +
          '<h3 class="mb-3 text-xs font-semibold uppercase tracking-wider text-accent">Page ' +
          page.page_number +
          "</h3>" +
          (empty
            ? '<p class="text-sm italic text-slate-500">(no text on this page)</p>'
            : '<div class="whitespace-pre-wrap">' + body + "</div>") +
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

  async function continueToGeneration() {
    if (!currentIntake) return;
    const response = await fetch(
      "/api/v1/pdf/" + currentIntake.intake_id + "/continue",
      { method: "POST" }
    );
    const payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      showActionMessage(formatApiError(payload, "Continue failed."), true);
      return;
    }
    const status = document.getElementById("progress-status");
    if (status) status.textContent = "Text validated";
    const project = document.getElementById("progress-project");
    if (project) project.textContent = currentIntake.filename;
    showActionMessage(payload.message || "Ready for generation (next phase).");
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

  if (btnCancel) {
    btnCancel.addEventListener("click", cancelIntake);
  }

  const btnStart = document.getElementById("btn-start");
  if (btnStart) {
    btnStart.addEventListener("click", function () {
      // TODO: TTS generation — start full pipeline when Phase 2 is ready
      console.info("[TODO] Start generation");
    });
  }

  const btnResume = document.getElementById("btn-resume");
  if (btnResume) {
    btnResume.addEventListener("click", function () {
      // TODO: retry system — resume previous job
      console.info("[TODO] Resume previous job");
    });
  }
})();
