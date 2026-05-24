/**
 * Gemini API token settings — file-backed CRUD.
 */

(function () {
  "use strict";

  const tokenList = document.getElementById("token-list");
  const btnAdd = document.getElementById("btn-add-token");
  const btnSave = document.getElementById("btn-save-tokens");
  const settingsMsg = document.getElementById("settings-msg");
  const runtimeTokenName = document.getElementById("runtime-token-name");
  const runtimeChunk = document.getElementById("runtime-chunk");
  const runtimeFailovers = document.getElementById("runtime-failovers");

  /** @type {Array<{name: string, api_key: string, api_key_masked?: string, enabled: boolean, priority?: number}>} */
  let tokens = [];
  let runtimeTimer = null;

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function showMsg(text, isError) {
    if (!settingsMsg) return;
    settingsMsg.textContent = text;
    settingsMsg.classList.remove("hidden", "text-red-400", "text-emerald-400", "text-slate-400");
    settingsMsg.classList.add(isError ? "text-red-400" : "text-emerald-400");
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

  function renderTokens() {
    if (!tokenList) return;
    if (!tokens.length) {
      tokenList.innerHTML =
        '<p class="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-sm text-slate-500">No tokens yet. Add your first Gemini API key.</p>';
      return;
    }

    tokenList.innerHTML = tokens
      .map(function (token, index) {
        const masked = token.api_key_masked || token.api_key || "";
        const keyValue = token.api_key && token.api_key.indexOf("•") < 0 ? token.api_key : "";
        return (
          '<article class="token-card rounded-xl border border-slate-700 bg-slate-900/50 p-4" data-index="' +
          index +
          '">' +
          '<div class="flex flex-wrap items-start justify-between gap-3">' +
          '<label class="flex cursor-pointer items-center gap-2 text-sm text-slate-300">' +
          '<input type="checkbox" class="token-enabled h-4 w-4 rounded border-slate-600 bg-slate-900 text-accent" ' +
          (token.enabled ? "checked" : "") +
          " />" +
          "<span>Enabled</span></label>" +
          '<span class="text-xs text-slate-500">Priority: <span class="font-medium text-slate-300">' +
          (index + 1) +
          "</span></span>" +
          '<div class="flex gap-2">' +
          '<button type="button" class="token-up rounded border border-slate-600 px-2 py-1 text-xs text-slate-400 hover:text-white" ' +
          (index === 0 ? "disabled" : "") +
          ">↑</button>" +
          '<button type="button" class="token-down rounded border border-slate-600 px-2 py-1 text-xs text-slate-400 hover:text-white" ' +
          (index === tokens.length - 1 ? "disabled" : "") +
          ">↓</button>" +
          '<button type="button" class="token-delete rounded border border-red-900/80 px-2 py-1 text-xs text-red-300 hover:border-red-600">Delete</button>' +
          "</div></div>" +
          '<div class="mt-4 grid gap-3 sm:grid-cols-2">' +
          '<div><label class="mb-1 block text-xs text-slate-500">Project name</label>' +
          '<input type="text" class="token-name w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100" value="' +
          escapeHtml(token.name) +
          '" dir="ltr" /></div>' +
          '<div><label class="mb-1 block text-xs text-slate-500">API key</label>' +
          '<input type="password" class="token-key w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 font-mono" ' +
          'placeholder="' +
          escapeHtml(masked) +
          '" value="' +
          escapeHtml(keyValue) +
          '" dir="ltr" autocomplete="off" /></div>' +
          "</div>" +
          '<div class="mt-3 flex flex-wrap items-center gap-3">' +
          '<button type="button" class="token-test rounded-lg border border-indigo-700 bg-indigo-950/50 px-3 py-1.5 text-xs font-semibold text-indigo-200 hover:border-indigo-500">Test token</button>' +
          '<span class="token-test-result text-xs text-slate-500"></span>' +
          "</div></article>"
        );
      })
      .join("");
  }

  function collectFromDom() {
    if (!tokenList) return [];
    const cards = tokenList.querySelectorAll(".token-card");
    const collected = [];
    cards.forEach(function (card, index) {
      const nameEl = card.querySelector(".token-name");
      const keyEl = card.querySelector(".token-key");
      const enabledEl = card.querySelector(".token-enabled");
      const prev = tokens[index] || {};
      const rawKey = keyEl ? keyEl.value.trim() : "";
      const apiKey = rawKey || prev.api_key_masked || prev.api_key || "";
      collected.push({
        name: nameEl ? nameEl.value.trim() : prev.name,
        api_key: apiKey,
        enabled: enabledEl ? enabledEl.checked : true,
      });
    });
    return collected;
  }

  async function loadTokens() {
    const response = await fetch("/api/v1/tokens");
    const data = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      showMsg(formatApiError(data, "Could not load tokens."), true);
      return;
    }
    tokens = (data.tokens || []).map(function (t) {
      return {
        name: t.name,
        api_key: t.api_key_masked,
        api_key_masked: t.api_key_masked,
        enabled: t.enabled,
        priority: t.priority,
      };
    });
    renderTokens();
  }

  async function saveTokens() {
    tokens = collectFromDom();
    const payload = {
      tokens: tokens.map(function (t) {
        return {
          name: t.name,
          api_key: t.api_key,
          enabled: t.enabled,
        };
      }),
    };

    btnSave.disabled = true;
    btnSave.textContent = "Saving…";
    try {
      const response = await fetch("/api/v1/tokens", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        throw new Error(formatApiError(data, "Save failed."));
      }
      tokens = (data.tokens || []).map(function (t) {
        return {
          name: t.name,
          api_key_masked: t.api_key_masked,
          api_key: t.api_key_masked,
          enabled: t.enabled,
        };
      });
      renderTokens();
      showMsg("Tokens saved.");
    } catch (err) {
      showMsg(err.message || "Save failed.", true);
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = "Save tokens";
    }
  }

  async function testToken(index) {
    const card = tokenList.querySelector('.token-card[data-index="' + index + '"]');
    if (!card) return;
    const nameEl = card.querySelector(".token-name");
    const keyEl = card.querySelector(".token-key");
    const resultEl = card.querySelector(".token-test-result");
    const body = {};
    if (keyEl && keyEl.value.trim()) {
      body.api_key = keyEl.value.trim();
    } else if (nameEl && nameEl.value.trim()) {
      body.name = nameEl.value.trim();
    } else {
      if (resultEl) resultEl.textContent = "Enter an API key to test.";
      return;
    }

    if (resultEl) resultEl.textContent = "Testing…";
    try {
      const response = await fetch("/api/v1/tokens/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        throw new Error(formatApiError(data, "Test failed."));
      }
      if (resultEl) resultEl.textContent = data.message || data.result;
    } catch (err) {
      if (resultEl) resultEl.textContent = err.message || "Test failed.";
    }
  }

  async function pollRuntime() {
    const response = await fetch("/api/v1/tokens/runtime-status");
    const data = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) return;

    if (!data.active) {
      if (runtimeTokenName) runtimeTokenName.textContent = "—";
      if (runtimeChunk) runtimeChunk.textContent = "Not generating";
      if (runtimeFailovers) runtimeFailovers.textContent = "—";
      return;
    }

    if (runtimeTokenName) {
      runtimeTokenName.textContent = data.current_token_name || "—";
    }
    if (runtimeChunk) {
      runtimeChunk.textContent =
        data.total_chunks > 0
          ? "chunk " + data.current_chunk + " / " + data.total_chunks
          : "—";
    }
    if (runtimeFailovers) {
      runtimeFailovers.textContent = String(data.quota_failovers || 0);
    }
  }

  function moveToken(index, direction) {
    tokens = collectFromDom();
    const target = index + direction;
    if (target < 0 || target >= tokens.length) return;
    const item = tokens.splice(index, 1)[0];
    tokens.splice(target, 0, item);
    renderTokens();
  }

  function addToken() {
    tokens = collectFromDom();
    tokens.push({
      name: "project-" + (tokens.length + 1),
      api_key: "",
      enabled: true,
    });
    renderTokens();
  }

  function deleteToken(index) {
    tokens = collectFromDom();
    tokens.splice(index, 1);
    renderTokens();
  }

  if (tokenList) {
    tokenList.addEventListener("click", function (event) {
      const card = event.target.closest(".token-card");
      if (!card) return;
      const index = parseInt(card.getAttribute("data-index"), 10);
      if (event.target.closest(".token-up")) moveToken(index, -1);
      if (event.target.closest(".token-down")) moveToken(index, 1);
      if (event.target.closest(".token-delete")) deleteToken(index);
      if (event.target.closest(".token-test")) testToken(index);
    });
  }

  if (btnAdd) btnAdd.addEventListener("click", addToken);
  if (btnSave) btnSave.addEventListener("click", saveTokens);

  loadTokens();
  pollRuntime();
  runtimeTimer = setInterval(pollRuntime, 2000);
})();
