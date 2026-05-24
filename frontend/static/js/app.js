/**
 * Audiobook Generator — frontend entry (placeholders only).
 * TODO: wire PDF upload, form submission, progress polling / WebSocket.
 */

(function () {
  "use strict";

  const form = document.getElementById("generation-form");
  const btnStart = document.getElementById("btn-start");
  const btnResume = document.getElementById("btn-resume");

  if (btnStart) {
    btnStart.addEventListener("click", function () {
      // TODO: POST /api/v1/jobs — start generation
      console.info("[placeholder] Start generation");
    });
  }

  if (btnResume) {
    btnResume.addEventListener("click", function () {
      // TODO: POST /api/v1/jobs/{id}/resume
      console.info("[placeholder] Resume previous job");
    });
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
    });
  }
})();
