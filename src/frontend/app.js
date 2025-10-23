// Calcula la URL base del backend. Preferimos hablar con el mismo origen

// para evitar problemas de CSP/CORS cuando se sirve tras Nginx.

const API = (function () {

  if (location.protocol === "file:") {

    return "http://127.0.0.1:5001/api";

  }

  return `${location.origin}/api`;

})();

const $ = (sel) => document.querySelector(sel);

const on = (el, ev, fn) => el && el.addEventListener(ev, fn);



function ensureToastsContainer() {

  let container = document.getElementById("toasts");

  if (!container) {

    container = document.createElement("div");

    container.id = "toasts";

    container.className = "toasts";

    document.body.appendChild(container);

  }

  return container;

}



function toast(msg, ok = false) {

  if (ok && typeof state !== "undefined" && state.preferences && state.preferences.realtimeToasts === false) {

    return;

  }

  const container = ensureToastsContainer();

  const node = document.createElement("div");

  node.className = `toast ${ok ? "ok" : "err"}`;

  node.setAttribute("role", "status");

  node.textContent = msg;

  node.classList.add("enter");

  container.appendChild(node);

  requestAnimationFrame(() => {

    node.classList.add("enter-active");

  });

  setTimeout(() => {

    node.classList.add("fade-out");

    node.addEventListener("transitionend", () => node.remove(), { once: true });

  }, 3400);

}



async function api(path, opts = {}) {

  const config = {

    credentials: "include",

    headers: { "Content-Type": "application/json" },

    ...opts,

  };

  const res = await fetch(`${API}${path}`, config);

  if (!res.ok) {

    let err = "Error de red";

    try {

      const json = await res.json();

      err = json.error?.message || err;

    } catch (_ignored) {}

    throw new Error(err);

  }

  const isJson = res.headers

    .get("content-type")

    ?.includes("application/json");

  return isJson ? res.json() : res.text();

}



const show = (el) => el.classList.remove("hide");

const hide = (el) => el.classList.add("hide");



function isNotFoundError(err) {

  const msg = (err?.message || "").toLowerCase();

  return msg.includes("no encontrada") || msg.includes("no existe") || msg.includes("notfound");

}



const currencyFormatter = new Intl.NumberFormat("es-AR", {

  style: "currency",

  currency: "USD",

  minimumFractionDigits: 2,

});



const formatCurrency = (value) => currencyFormatter.format(Number(value || 0));



function escapeHtml(value) {

  return String(value || "")

    .replace(/&/g, "&amp;")

    .replace(/</g, "&lt;")

    .replace(/>/g, "&gt;")

    .replace(/"/g, "&quot;")

    .replace(/'/g, "&#39;");

}



function formatDateTime(value) {

  if (!value) return "â€”";

  const normalised = typeof value === "string" ? value.replace("T", " ") : value;

  const date = new Date(normalised);

  if (Number.isNaN(date.getTime())) {

    return typeof value === "string" ? value : "â€”";

  }

  return date.toLocaleString();

}



function formatDateOnly(value) {

  if (!value) return "â€”";

  const normalised = typeof value === "string" ? value.replace("T", " ") : value;

  const date = new Date(normalised);

  if (Number.isNaN(date.getTime())) {

    return typeof value === "string" ? value : "â€”";

  }

  return date.toLocaleDateString();

}



function formatPercentage(value) {

  const numeric = Number(value);

  if (!Number.isFinite(numeric) || numeric <= 0) {

    return "0%";

  }

  if (numeric >= 100) {

    return "100%";

  }

  const digits = numeric >= 10 ? 0 : 1;

  return `${numeric.toFixed(digits)}%`;

}



const ICONS = {

  pencil: `

    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">

      <path d="M3 17.25V21h3.75l11-11-3.75-3.75-11 11ZM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83Z"></path>

    </svg>

  `,

  plus: `

    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">

      <path d="M13 11V5a1 1 0 0 0-2 0v6H5a1 1 0 0 0 0 2h6v6a1 1 0 0 0 2 0v-6h6a1 1 0 0 0 0-2Z"></path>

    </svg>

  `,

};



const centersRequestState = {

  modal: null,

  selected: new Set(),

  options: [],

  existing: new Set(),

  keyListenerBound: false,

};



const ANIMATED_SELECTORS = [

  ".pane",

  ".card",

  ".metric-card",

  ".notification-item",

  ".detail-section",

  ".content-section > *:not(.page-header)",

  ".admin-material-detail",

  ".admin-user-detail",

  ".archivos-adjuntos",

];

const REDUCED_MOTION_MEDIA = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

const dynamicFilterHandlers = new WeakMap();

let animationObserver = null;

let effectsEnabled = true;

let headerNavInitialized = false;



function markAnimatedElements(scope = document) {

  if (!scope || (scope === document && !document.body)) {

    return [];

  }

  const nodes = new Set();

  ANIMATED_SELECTORS.forEach((selector) => {

    scope.querySelectorAll(selector).forEach((element) => {

      if (!element.dataset.animate) {

        element.dataset.animate = "fade-up";

      }

      nodes.add(element);

    });

  });

  scope.querySelectorAll("[data-animate]").forEach((element) => nodes.add(element));

  return Array.from(nodes);

}



function teardownAnimations() {

  if (animationObserver) {

    animationObserver.disconnect();

    animationObserver = null;

  }

}



function refreshAnimations(scope = document) {

  const elements = markAnimatedElements(scope);

  if (!elements.length) {

    return;

  }

  if (!effectsEnabled) {

    elements.forEach((el) => el.classList.add("is-visible"));

    teardownAnimations();

    return;

  }

  if (REDUCED_MOTION_MEDIA && REDUCED_MOTION_MEDIA.matches) {

    elements.forEach((el) => el.classList.add("is-visible"));

    teardownAnimations();

    return;

  }

  if (!animationObserver) {

    animationObserver = new IntersectionObserver(

      (entries) => {

        entries.forEach((entry) => {

          if (entry.isIntersecting) {

            entry.target.classList.add("is-visible");

            animationObserver.unobserve(entry.target);

          }

        });

      },

      { threshold: 0.12, rootMargin: "0px 0px -10%" },

    );

  }

  elements.forEach((el) => {

    if (animationObserver) {

      animationObserver.observe(el);

    }

  });

}



function applyEffectsPreference(enabled) {

  effectsEnabled = enabled;

  document.documentElement.dataset.effects = enabled ? "on" : "off";

  if (document.body) {

    document.body.dataset.effects = enabled ? "on" : "off";

  }

  if (enabled) {

    document.documentElement.style.removeProperty("--current-motion-scale");

    refreshAnimations();

  } else {

    teardownAnimations();

    document.querySelectorAll("[data-animate]").forEach((el) => {

      el.classList.add("is-visible");

    });

  }

}



const skeletonRegistry = new WeakMap();



function showTableSkeleton(target, { rows = 6, columns = null } = {}) {

  const table = typeof target === "string" ? document.querySelector(target) : target;

  if (!table) {

    return () => {};

  }

  const tbody = table.tBodies?.[0] || table.querySelector("tbody");

  if (!tbody) {

    return () => {};

  }

  const colCount = columns || table.tHead?.rows?.[0]?.cells?.length || 4;

  const skeletonRows = [];

  for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {

    const tr = document.createElement("tr");

    tr.className = "skeleton-row";

    for (let colIndex = 0; colIndex < colCount; colIndex += 1) {

      const td = document.createElement("td");

      const span = document.createElement("span");

      span.className = "skeleton skeleton-line";

      td.appendChild(span);

      tr.appendChild(td);

    }

    tbody.appendChild(tr);

    skeletonRows.push(tr);

  }

  skeletonRegistry.set(table, skeletonRows);

  return () => {

    (skeletonRegistry.get(table) || []).forEach((row) => row.remove());

    skeletonRegistry.delete(table);

  };

}



function setButtonLoading(button, isLoading) {

  if (!button) {

    return;

  }

  if (isLoading) {

    button.dataset.loading = "true";

    button.classList.add("is-loading");

    button.setAttribute("aria-busy", "true");

  } else {

    button.dataset.loading = "false";

    button.classList.remove("is-loading");

    button.removeAttribute("aria-busy");

  }

}



function initDynamicFilters(scope = document) {

  scope.querySelectorAll('[data-filter-target]').forEach((input) => {

    if (dynamicFilterHandlers.has(input)) {

      return;

    }

    const targetSelector = input.dataset.filterTarget;

    const itemsSelector = input.dataset.filterItems || "tr";

    const emptySelector = input.dataset.filterEmpty || "";

    const target = document.querySelector(targetSelector);

    if (!target) {

      return;

    }

    const handler = () => {

      const value = (input.value || "").trim().toLowerCase();

      const items = target.querySelectorAll(itemsSelector);

      let visibleCount = 0;

      items.forEach((item) => {

        const matches = !value || (item.textContent || "").toLowerCase().includes(value);

        item.style.display = matches ? "" : "none";

        if (matches) {

          visibleCount += 1;

        }

      });

      if (emptySelector) {

        const emptyNode = document.querySelector(emptySelector);

        if (emptyNode) {

          emptyNode.style.display = visibleCount === 0 ? "block" : "none";

        }

      }

    };

    input.addEventListener("input", handler);

    dynamicFilterHandlers.set(input, handler);

    handler();

  });

}



function setSubmenuTabState(submenu, enabled) {

  if (!submenu) {

    return;

  }

  const focusable = submenu.querySelectorAll("a,button");

  focusable.forEach((node) => {

    if (enabled) {

      node.removeAttribute("tabindex");

    } else {

      node.setAttribute("tabindex", "-1");

    }

  });

}



function closeSubmenu(item) {

  if (!item) {

    return;

  }

  const trigger = item.querySelector(":scope > .app-menu__trigger");

  const submenu = item.querySelector(":scope > .app-submenu");

  item.classList.remove("is-open");

  if (trigger) {

    trigger.setAttribute("aria-expanded", "false");

  }

  if (submenu) {

    submenu.hidden = true;

    submenu.setAttribute("aria-hidden", "true");

    setSubmenuTabState(submenu, false);

    submenu.querySelectorAll(".has-submenu").forEach((child) => {

      if (child !== item) {

        closeSubmenu(child);

      }

    });

  }

}



function openSubmenu(item) {

  if (!item) {

    return;

  }

  const trigger = item.querySelector(":scope > .app-menu__trigger");

  const submenu = item.querySelector(":scope > .app-submenu");

  item.classList.add("is-open");

  if (trigger) {

    trigger.setAttribute("aria-expanded", "true");

  }

  if (submenu) {

    submenu.hidden = false;

    submenu.removeAttribute("hidden");

    submenu.setAttribute("aria-hidden", "false");

    setSubmenuTabState(submenu, true);

  }

}



function closeAllSubmenus(except = null, scope = document) {

  scope.querySelectorAll(".has-submenu").forEach((item) => {

    if (item === except) {

      return;

    }

    closeSubmenu(item);

  });

}



function initializeHeaderSubmenus(root = document) {

  root.querySelectorAll(".has-submenu").forEach((item) => {

    closeSubmenu(item);

  });

}



function setupHeaderNav() {

  const nav = document.getElementById("primaryNav");

  if (!nav) return;



  initializeHeaderSubmenus(nav);



  nav.addEventListener("click", (event) => {

    const trigger = event.target instanceof Element ? event.target.closest(".app-menu__trigger") : null;

    if (trigger && nav.contains(trigger)) {

      event.preventDefault();

      const item = trigger.closest(".has-submenu");

      if (!item) return;

      const isOpen = item.classList.contains("is-open");

      closeAllSubmenus(item, nav);

      if (isOpen) {

        closeSubmenu(item);

      } else {

        openSubmenu(item);

      }

      return;

    }

    const link = event.target instanceof Element ? event.target.closest(".app-menu__link") : null;

    if (link && nav.contains(link)) {

      closeAllSubmenus(null, nav);

    }

  });



  nav.addEventListener("keydown", (event) => {

    const trigger = event.target instanceof Element ? event.target.closest(".app-menu__trigger") : null;

    if (!trigger || !nav.contains(trigger)) {

      return;

    }

    const item = trigger.closest(".has-submenu");

    if (!item) {

      return;

    }

    if (event.key === "Escape") {

      event.preventDefault();

      closeSubmenu(item);

      trigger.focus({ preventScroll: true });

      return;

    }

    if (event.key === "ArrowDown") {

      event.preventDefault();

      if (!item.classList.contains("is-open")) {

        closeAllSubmenus(item, nav);

        openSubmenu(item);

      }

      const submenu = item.querySelector(":scope > .app-submenu");

      if (submenu) {

        const firstFocusable = submenu.querySelector("a,button");

        firstFocusable?.focus({ preventScroll: true });

      }

    }

  });



  nav.addEventListener("focusout", (event) => {

    if (!nav.contains(event.relatedTarget)) {

      closeAllSubmenus(null, nav);

    }

  });



  document.addEventListener("click", (event) => {

    if (!nav.contains(event.target)) {

      closeAllSubmenus(null, nav);

    }

  });

}



function finalizePage(scope = document) {

  document.body?.classList.add("is-ready");

  markAnimatedElements(scope);

  refreshAnimations(scope);

  initDynamicFilters(scope);

  setupHeaderNav();

  configureRequestsMenu();

}



const tableSortStates = new WeakMap();



function refreshSortableTables(root = document) {

  const scope = root instanceof Element ? root : document;

  scope.querySelectorAll("table[data-sortable-table]").forEach((table) => {

    ensureTableSortable(table);

  });

}



function ensureTableSortable(target) {

  const table = typeof target === "string" ? document.querySelector(target) : target;

  if (!table) {

    return;

  }

  let state = tableSortStates.get(table);

  if (!state) {

    state = { column: null, direction: 1 };

    tableSortStates.set(table, state);

    initTableSortable(table, state);

  }

  updateSortIndicators(table, state);

  if (typeof state.column === "number") {

    sortTableRows(table, state.column, state.direction, { preserveState: true });

  }

}



function initTableSortable(table, state) {

  if (!table || table.dataset.sortableInit === "1") {

    return;

  }

  const thead = table.querySelector("thead");

  if (!thead) {

    return;

  }

  table.dataset.sortableInit = "1";

  const headers = Array.from(thead.querySelectorAll("th"));

  headers.forEach((th, index) => {

    const rawLabel = (th.textContent || "").trim() || `Columna ${index + 1}`;

    const safeLabel = escapeHtml(rawLabel);

    const button = document.createElement("button");

    button.type = "button";

    button.className = "sort-button";

    button.dataset.label = rawLabel;

    button.innerHTML = `<span class="sort-label">${safeLabel}</span><span class="sort-icon">A-Z</span>`;

    button.addEventListener("click", () => {

      let nextDirection = 1;

      if (state.column === index) {

        nextDirection = state.direction === 1 ? -1 : 1;

      }

      state.column = index;

      state.direction = nextDirection;

      sortTableRows(table, index, nextDirection);

      updateSortIndicators(table, state);

    });

    th.classList.add("sortable");

    th.setAttribute("data-sort", "none");

    th.replaceChildren(button);

  });

}



function sortTableRows(table, columnIndex, direction, options = {}) {

  if (!table || !table.tBodies || !table.tBodies.length) {

    return;

  }

  const tbody = table.tBodies[0];

  const rows = Array.from(tbody.querySelectorAll("tr"));

  if (!rows.length) {

    return;

  }

  const multiplier = direction === -1 ? -1 : 1;

  rows.sort((rowA, rowB) => {

    const aToken = getCellSortToken(rowA, columnIndex);

    const bToken = getCellSortToken(rowB, columnIndex);

    if (aToken.type === bToken.type) {

      if (aToken.type === "number" || aToken.type === "date") {

        return (aToken.value - bToken.value) * multiplier;

      }

      return aToken.value.localeCompare(bToken.value, "es", {

        sensitivity: "base",

        numeric: true,

      }) * multiplier;

    }

    return aToken.raw.localeCompare(bToken.raw, "es", {

      sensitivity: "base",

      numeric: true,

    }) * multiplier;

  });

  rows.forEach((row) => tbody.appendChild(row));

  if (!options.preserveState) {

    const state = tableSortStates.get(table);

    if (state) {

      state.column = columnIndex;

      state.direction = multiplier;

    }

  }



  refreshSortableTables();

}



function getCellSortToken(row, columnIndex) {

  const cell = row.cells?.[columnIndex];

  if (!cell) {

    return { type: "string", value: "", raw: "" };

  }

  const dataValue = cell.getAttribute("data-sort");

  const raw = (dataValue ?? cell.textContent ?? "").trim();

  const numeric = parseNumericValue(raw);

  if (numeric !== null) {

    return { type: "number", value: numeric, raw };

  }

  const parsedDate = Date.parse(raw);

  if (!Number.isNaN(parsedDate)) {

    return { type: "date", value: parsedDate, raw };

  }

  return { type: "string", value: raw.toLowerCase(), raw };

}



function parseNumericValue(raw) {

  if (!raw) {

    return null;

  }

  const normalized = raw

    .replace(/\s+/g, "")

    .replace(/[^0-9,.-]/g, "");

  if (!normalized) {

    return null;

  }

  let candidate = normalized;

  if (candidate.includes(",") && (!candidate.includes(".") || candidate.lastIndexOf(",") > candidate.lastIndexOf("."))) {

    candidate = candidate.replace(/\./g, "").replace(",", ".");

  } else {

    candidate = candidate.replace(/,/g, "");

  }

  if (!candidate || candidate === "-" || candidate === ".") {

    return null;

  }

  const numeric = Number(candidate);

  return Number.isFinite(numeric) ? numeric : null;

}



function updateSortIndicators(table, state) {

  if (!table) {

    return;

  }

  const thead = table.querySelector("thead");

  if (!thead) {

    return;

  }

  const headers = thead.querySelectorAll("th.sortable");

  headers.forEach((th, index) => {

    const button = th.querySelector("button.sort-button");

    const icon = button?.querySelector(".sort-icon");

    const baseLabel = button?.dataset.label || (th.textContent || "").trim() || `Columna ${index + 1}`;

    const isActive = state && state.column === index;

    if (icon) {

      if (isActive) {

        icon.textContent = state.direction === -1 ? "Z-A" : "A-Z";

        th.setAttribute("data-sort", state.direction === -1 ? "desc" : "asc");

      } else {

        icon.textContent = "A-Z";

        th.setAttribute("data-sort", "none");

      }

    }

    if (button) {

      const dirLabel = isActive ? (state.direction === -1 ? "Z-A" : "A-Z") : "A-Z";

      button.setAttribute("aria-label", `Ordenar por ${baseLabel}${isActive ? ` (${dirLabel})` : ""}`);

    }

  });

}



function trimChatHistory() {

  const max = CHAT_HISTORY_LIMIT * 2;

  if (state.chat.messages.length > max) {

    state.chat.messages = state.chat.messages.slice(-max);

  }

}



function renderChatMessages() {

  const container = document.getElementById("chatbotMessages");

  if (!container) {

    return;

  }

  container.innerHTML = "";

  if (!state.chat.messages.length) {

    const empty = document.createElement("div");

    empty.className = "chatbot-empty";

    empty.textContent = "Todavia no iniciaste una conversacion. Escribi tu consulta.";

    container.appendChild(empty);

    return;

  }

  const fragment = document.createDocumentFragment();

  state.chat.messages.forEach((msg) => {

    const wrapper = document.createElement("div");

    const role = msg.role === "assistant" ? "assistant" : "user";

    wrapper.className = `chatbot-message chatbot-message--${role}`;

    wrapper.innerHTML = `<p>${escapeHtml(msg.content)}</p>`;

    fragment.appendChild(wrapper);

  });

  container.appendChild(fragment);

  container.scrollTop = container.scrollHeight;

}



function updateChatbotControls() {

  const input = document.getElementById("chatbotInput");

  const sendBtn = document.getElementById("chatbotSend");

  const status = document.getElementById("chatbotStatus");

  if (input) {

    input.disabled = state.chat.isSending;

  }

  if (sendBtn) {

    sendBtn.disabled = state.chat.isSending;

    sendBtn.textContent = state.chat.isSending ? "Enviando..." : "Enviar";

  }

  if (status) {

    status.textContent = state.chat.isSending ? "Consultando modelo..." : "";

  }

}



function toggleChatbotPanel(forceState) {

  const panel = document.getElementById("chatbotPanel");

  const fab = document.getElementById("chatbotFab");

  if (!panel || !fab) {

    return;

  }

  const nextState = typeof forceState === "boolean" ? forceState : !state.chat.isOpen;

  state.chat.isOpen = nextState;

  panel.classList.toggle("chatbot-panel--open", nextState);

  panel.setAttribute("aria-hidden", nextState ? "false" : "true");

  fab.classList.toggle("chatbot-fab--hidden", nextState);

  if (nextState) {

    renderChatMessages();

    const input = document.getElementById("chatbotInput");

    if (input) {

      input.focus();

    }

  }

}



async function processChatbotPrompt(rawText) {

  const text = String(rawText || "").trim();

  if (!text || state.chat.isSending) {

    return;

  }

  const historyPayload = state.chat.messages.slice(-(CHAT_HISTORY_LIMIT - 1)).map((msg) => ({

    role: msg.role,

    content: msg.content,

  }));

  const userMessage = { role: "user", content: text };

  state.chat.messages.push(userMessage);

  trimChatHistory();

  renderChatMessages();



  state.chat.isSending = true;

  updateChatbotControls();



  try {

    const resp = await api("/chatbot", {

      method: "POST",

      body: JSON.stringify({ message: text, history: historyPayload }),

    });

    if (!resp?.ok) {

      throw new Error(resp?.error?.message || "No se obtuvo respuesta");

    }

    const reply = String(resp.message?.content || "No recibimos respuesta del asistente.").trim();

    state.chat.messages.push({ role: "assistant", content: reply });

  } catch (err) {

    const detail = err?.message || "No se pudo contactar al asistente";

    state.chat.messages.push({ role: "assistant", content: `Hubo un problema: ${detail}` });

    toast(detail);

  } finally {

    trimChatHistory();

    state.chat.isSending = false;

    renderChatMessages();

    updateChatbotControls();

  }

}



function ensureChatbotWidget() {

  if (document.getElementById("chatbotFab")) {

    return;

  }

  const fab = document.createElement("button");

  fab.id = "chatbotFab";

  fab.type = "button";

  fab.className = "chatbot-fab";

  fab.innerHTML = `

    <img src="assets/chatbot-icon.svg" alt="Abrir asistente" class="chatbot-fab__icon" aria-hidden="true"/>

    <span class="sr-only">Chat con asistente</span>

  `;

  document.body.appendChild(fab);



  const panel = document.createElement("section");

  panel.id = "chatbotPanel";

  panel.className = "chatbot-panel";

  panel.setAttribute("aria-hidden", "true");

  panel.innerHTML = `

    <header class="chatbot-panel__header">

      <span class="chatbot-panel__title">Asistente SPM</span>

      <button type="button" class="chatbot-panel__close" id="chatbotClose" aria-label="Cerrar asistente">X</button>

    </header>

    <div class="chatbot-panel__messages" id="chatbotMessages"></div>

    <p class="chatbot-panel__status" id="chatbotStatus"></p>

    <form class="chatbot-panel__form" id="chatbotForm">

      <label for="chatbotInput" class="sr-only">Mensaje para el asistente</label>

      <textarea id="chatbotInput" rows="3" placeholder="Escribi tu consulta..." required></textarea>

      <div class="chatbot-panel__actions">

        <button type="submit" id="chatbotSend" class="btn">Enviar</button>

      </div>

    </form>

  `;

  document.body.appendChild(panel);



  fab.addEventListener("click", () => {

    toggleChatbotPanel(true);

  });



  const closeBtn = document.getElementById("chatbotClose");

  if (closeBtn) {

    closeBtn.addEventListener("click", (ev) => {

      ev.preventDefault();

      toggleChatbotPanel(false);

    });

  }



  const form = document.getElementById("chatbotForm");

  const input = document.getElementById("chatbotInput");

  if (form) {

    form.addEventListener("submit", async (ev) => {

      ev.preventDefault();

      if (!input) {

        return;

      }

      const value = input.value;

      if (!value.trim() || state.chat.isSending) {

        return;

      }

      input.value = "";

      await processChatbotPrompt(value);

    });

  }

  if (input) {

    input.addEventListener("keydown", (ev) => {

      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {

        ev.preventDefault();

        form?.dispatchEvent(new Event("submit", { cancelable: true }));

      }

    });

  }



  document.addEventListener("keydown", (ev) => {

    if (ev.key === "Escape" && state.chat.isOpen) {

      toggleChatbotPanel(false);

    }

  });
}



function initChatbotWidget() {

  ensureChatbotWidget();

  if (!state.chat.messages.length) {

    state.chat.messages.push({

      role: "assistant",

      content: "Hola, soy el asistente de SPM. En que puedo ayudarte hoy?",

    });

  }

  renderChatMessages();

  updateChatbotControls();

}



function initHomeHero(userName) {

  const node = document.getElementById("homeTypewriter");

  if (!node || node.dataset.typewriterDone === "1") {

    return;

  }

  const template = node.dataset.typewriter || node.textContent || "";

  const message = template.replace(/\{\{\s*name\s*\}\}/gi, userName || "").replace(/\s{2,}/g, " ").trim();

  if (!message) {

    node.classList.add("is-finished");

    node.dataset.typewriterDone = "1";

    return;

  }

  node.textContent = "";

  node.dataset.typewriterDone = "1";

  node.classList.add("is-typing");

  let index = 0;

  const delay = Number(node.dataset.typewriterSpeed) || 48;

  const initialDelay = Number(node.dataset.typewriterDelay) || 260;



  const tick = () => {

    index += 1;

    node.textContent = message.slice(0, index);

    if (index < message.length) {

      window.setTimeout(tick, delay);

    } else {

      node.classList.remove("is-typing");

      node.classList.add("is-finished");

    }

  };



  window.setTimeout(tick, initialDelay);

}



const STATUS_LABELS = {

  draft: "Borrador",

  finalizada: "Finalizada",

  cancelada: "Cancelada",

  pendiente_de_aprobacion: "Pendiente de aprobaciÃ³n",

  pendiente: "Pendiente",

  aprobada: "Aprobada",

  rechazada: "Rechazada",

  cancelacion_pendiente: "CancelaciÃ³n pendiente",

  cancelacion_rechazada: "CancelaciÃ³n rechazada",

};



const PENDING_SOLICITUD_KEY = "pendingSolicitudId";

const PREFS_STORAGE_KEY = "spmPreferences";

const DEFAULT_PREFERENCES = {

  emailAlerts: true,

  realtimeToasts: true,

  approvalDigest: false,

  digestHour: "08:30",

  theme: "auto",

  density: "comfortable",

  rememberFilters: true,

  keyboardShortcuts: false,

};



const FILTER_STORAGE_PREFIX = "spmFilters:";

const KNOWN_FILTER_KEYS = ["adminUsers", "adminMateriales", "adminSolicitudes"];

const SYSTEM_THEME_MEDIA = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

let systemThemeListener = null;

let keyboardHandler = null;



function storageKeyForFilters(key) {

  return `${FILTER_STORAGE_PREFIX}${key}`;

}



function loadStoredFilters(key, fallback = {}) {

  if (!state.preferences?.rememberFilters) {

    return { ...fallback };

  }

  try {

    const raw = localStorage.getItem(storageKeyForFilters(key));

    if (!raw) {

      return { ...fallback };

    }

    const parsed = JSON.parse(raw);

    return { ...fallback, ...parsed };

  } catch (_err) {

    return { ...fallback };

  }

}



function saveStoredFilters(key, value) {

  if (!state.preferences?.rememberFilters) {

    localStorage.removeItem(storageKeyForFilters(key));

    return;

  }

  try {

    localStorage.setItem(storageKeyForFilters(key), JSON.stringify(value));

  } catch (_err) {

    console.warn("No se pudieron guardar filtros para", key);

  }

}



function clearStoredFilters(key) {

  localStorage.removeItem(storageKeyForFilters(key));

}



function clearAllStoredFilters() {

  KNOWN_FILTER_KEYS.forEach((key) => clearStoredFilters(key));

}



function statusBadge(status) {

  const normalized = (status || "").toLowerCase();

  const fallback = normalized ? normalized.replace(/_/g, " ") : "â€”";

  const label = STATUS_LABELS[normalized] || fallback;

  const pretty = STATUS_LABELS[normalized]

    ? label

    : label.charAt(0).toUpperCase() + label.slice(1);

  return `<span class="status-pill status-${normalized || "desconocido"}">${pretty}</span>`;

}



const DEFAULT_CENTROS = ["1008", "1050", "1500"];



const DEFAULT_ALMACENES_VIRTUALES = [

  { id: "AV-CENTRAL", label: "AV-CENTRAL - AlmacÃ©n Central" },

  { id: "AV-MANT", label: "AV-MANT - DepÃ³sito de Mantenimiento" },

  { id: "AV-REP", label: "AV-REP - Repuestos CrÃ­ticos" },

  { id: "AV-SERV", label: "AV-SERV - Servicios Industriales" },

];



const MATERIAL_SUGGESTION_LIMIT = 100000;



const ADMIN_CONFIG_FIELDS = {

  centros: ["codigo", "nombre", "descripcion", "notas", "activo"],

  almacenes: ["codigo", "nombre", "centro_codigo", "descripcion", "activo"],

  roles: ["nombre", "descripcion", "activo"],

  puestos: ["nombre", "descripcion", "activo"],

  sectores: ["nombre", "descripcion", "activo"],

};



const ADMIN_CONFIG_TABLE_FIELDS = {

  centros: ["codigo", "nombre", "descripcion", "notas", "activo"],

  almacenes: ["codigo", "nombre", "centro_codigo", "descripcion", "activo"],

  roles: ["nombre", "descripcion", "activo"],

  puestos: ["nombre", "descripcion", "activo"],

  sectores: ["nombre", "descripcion", "activo"],

};



const ADMIN_CONFIG_LABELS = {

  centros: "centro logÃ­stico",

  almacenes: "almacÃ©n virtual",

  roles: "rol",

  puestos: "puesto",

  sectores: "sector",

};



const CATALOG_KEYS = ["centros", "almacenes", "roles", "puestos", "sectores"];



function getCatalogItems(resource, { activeOnly = true } = {}) {

  if (!resource) {

    return [];

  }

  const items = Array.isArray(state.catalogs?.[resource]) ? state.catalogs[resource] : [];

  if (!activeOnly) {

    return [...items];

  }

  return items.filter((item) => item && item.activo !== false);

}



function setCatalogItems(resource, items) {

  if (!resource) {

    return;

  }

  state.catalogs[resource] = Array.isArray(items) ? items : [];

  refreshCatalogConsumers(resource);

}



function ensureCatalogDefaults(data = {}) {

  CATALOG_KEYS.forEach((key) => {

    if (!Array.isArray(data[key])) {

      data[key] = [];

    }

  });

  return data;

}



function updateDatalist(nodeId, values) {

  const node = document.getElementById(nodeId);

  if (!node) {

    return;

  }

  const unique = Array.from(new Set(values.filter(Boolean)));

  node.innerHTML = unique.map((value) => `<option value="${escapeHtml(value)}"></option>`).join("");

}



function refreshCatalogConsumers(resource = null) {

  const targets = resource ? [resource] : CATALOG_KEYS;

  if (targets.includes("roles")) {

    updateDatalist("catalogRolesList", getCatalogItems("roles", { activeOnly: true }).map((item) => item.nombre));

  }

  if (targets.includes("puestos")) {

    updateDatalist("catalogPuestosList", getCatalogItems("puestos", { activeOnly: true }).map((item) => item.nombre));

  }

  if (targets.includes("sectores")) {

    updateDatalist("catalogSectoresList", getCatalogItems("sectores", { activeOnly: true }).map((item) => item.nombre));

  }

}



function logCatalogWarnings(resource, warnings) {

  if (!Array.isArray(warnings) || !warnings.length) {

    return;

  }

  warnings.forEach((warning) => {

    if (!warning) {

      return;

    }

    const target = warning.resource || resource || "catalogos";

    const message = warning.message || (typeof warning === "string" ? warning : JSON.stringify(warning));

    console.info("[catalogos] aviso", { resource: target, message });

  });

}



async function loadCatalogData(resource = null, { silent = false, includeInactive = false } = {}) {

  if (!state.me) {

    return null;

  }

  try {

    const params = new URLSearchParams();

    if (includeInactive) {

      params.set("include_inactive", "1");

    }

    if (resource) {

      const endpoint = params.size ? `/catalogos/${resource}?${params.toString()}` : `/catalogos/${resource}`;

      const resp = await api(endpoint);

      if (!resp?.ok) {

        throw new Error(resp?.error?.message || "No se pudo cargar el catalogo");

      }

      logCatalogWarnings(resource, resp.warnings);

      setCatalogItems(resource, resp.items || []);

      if (!silent) {

        toast(`Cat?logo de ${adminConfigLabel(resource)} actualizado`, true);

      }

      return resp.items || [];

    }

    const endpoint = params.size ? `/catalogos?${params.toString()}` : "/catalogos";

    const resp = await api(endpoint);

    if (!resp?.ok) {

      throw new Error(resp?.error?.message || "No se pudo cargar la configuracion");

    }

    logCatalogWarnings(null, resp.warnings);

    const normalized = ensureCatalogDefaults(resp.data || {});

    CATALOG_KEYS.forEach((key) => {

      setCatalogItems(key, normalized[key]);

    });

    if (!silent) {

      toast("Cat?logos sincronizados", true);

    }

    return normalized;

  } catch (err) {

    console.error(err);

    if (!silent) {

      toast(err.message || "No se pudieron cargar los catalogos");

    }

    return null;

  }

}



function catalogueOptionLabel(code, name, extra) {

  const parts = [code];

  const printableName = (name || "").trim();

  if (printableName && printableName.toUpperCase() !== String(code || "").toUpperCase()) {

    parts.push(printableName);

  }

  if (extra) {

    parts.push(extra);

  }

  return parts.join(" - ");

}



function canViewTeamRequests() {

  const posicion = (state.me?.posicion || "").toLowerCase();

  const role = (state.me?.rol || "").toLowerCase();

  return posicion.includes("jefe") || posicion.includes("gerente") || role.includes("jefe") || role.includes("gerente");

}



function configureRequestsMenu() {

  const requestsMenu = document.querySelector('[data-menu="solicitudes"] .app-submenu');

  if (!requestsMenu) {

    return;

  }



  // Always show "Mis solicitudes" and "Crear solicitud"

  let menuHtml = `

    <a href="mis-solicitudes.html" class="app-submenu__link" role="menuitem">Mis solicitudes</a>

    <a href="crear-solicitud.html" class="app-submenu__link" role="menuitem">Crear solicitud</a>

  `;



  // Add "Solicitudes de mi Equipo" for managers

  if (canViewTeamRequests()) {

    menuHtml += `<a href="equipo-solicitudes.html" class="app-submenu__link" role="menuitem">Solicitudes de mi Equipo</a>`;

  }



  requestsMenu.innerHTML = menuHtml;

}



// Nueva funcionalidad para la pÃ¡gina de solicitudes del equipo

async function loadEquipoSolicitudes() {

  try {

    const response = await api("/solicitudes/equipo");

    if (!response.ok) {

      throw new Error(response.error?.message || "Error al cargar solicitudes del equipo");

    }



    const solicitudes = response.items || [];

    renderEquipoSolicitudes(solicitudes);

  } catch (err) {

    console.error(err);

    toast(err.message || "Error al cargar solicitudes del equipo");

  }

}



function renderEquipoSolicitudes(solicitudes) {

  const tbody = $("#equipoSolicitudesTableBody");

  if (!tbody) return;



  tbody.innerHTML = "";



  if (solicitudes.length === 0) {

    const emptyRow = document.createElement("tr");

    emptyRow.innerHTML = `<td colspan="8" style="text-align: center; padding: 2rem;">No hay solicitudes de tu equipo</td>`;

    tbody.appendChild(emptyRow);

    return;

  }



  solicitudes.forEach(solicitud => {

    const row = document.createElement("tr");



    const fecha = formatDateTime(solicitud.created_at);

    const estado = getEstadoLabel(solicitud.status);

    const total = formatCurrency(solicitud.total_monto || 0);

    const solicitante = solicitud.solicitante || solicitud.id_usuario || "Desconocido";



    row.innerHTML = `

      <td>${solicitud.id}</td>

      <td>${fecha}</td>

      <td>${solicitante}</td>

      <td>${solicitud.centro || ""}</td>

      <td><span class="status status--${solicitud.status}">${estado}</span></td>

      <td>${solicitud.planner_nombre || "No asignado"}</td>

      <td>${total}</td>

      <td>

        <button type="button" class="btn btn--small" onclick="openSolicitudDetail(${solicitud.id})">

          Ver detalle

        </button>

      </td>

    `;



    tbody.appendChild(row);

  });

}



function getEstadoLabel(status) {

  const labels = {

    "draft": "Borrador",

    "approved": "Aprobada",

    "en_tratamiento": "En tratamiento",

    "completed": "Completada",

    "cancelled": "Cancelada"

  };

  return labels[status] || status;

}



// InicializaciÃ³n de la pÃ¡gina de equipo

function initEquipoSolicitudesPage() {

  loadEquipoSolicitudes();



  // Configurar filtros

  const filterBtn = $("#equipoFilterBtn");

  if (filterBtn) {

    filterBtn.addEventListener("click", () => {

      loadEquipoSolicitudes(); // Por ahora recarga todo, despuÃ©s se puede filtrar en cliente

    });

  }

}



// Reportes functions

async function loadReportesEstadisticas() {

  try {

    const response = await api("/reportes/estadisticas");

    if (!response.ok) {

      throw new Error(response.error?.message || "Error al cargar estadÃ­sticas");

    }



    const data = response.estadisticas;

    renderEstadisticas(data);



    // Renderizar grÃ¡ficos si Chart.js estÃ¡ disponible

    if (typeof Chart !== 'undefined') {

      renderEstadoChart(response.por_estado || []);

      renderCentroChart(response.por_centro || []);

      renderTendenciaChart(response.tendencia_mensual || []);

    }

  } catch (err) {

    console.error(err);

    toast(err.message || "Error al cargar estadÃ­sticas");

  }

}



function renderEstadisticas(data) {

  const totalSpan = $("#totalSolicitudes");

  const activasSpan = $("#solicitudesActivas");

  const completadasSpan = $("#solicitudesCompletadas");

  const montoSpan = $("#montoTotal");



  if (totalSpan) totalSpan.textContent = data.total_solicitudes || 0;

  if (activasSpan) activasSpan.textContent = data.solicitudes_activas || 0;

  if (completadasSpan) completadasSpan.textContent = data.solicitudes_completadas || 0;

  if (montoSpan) montoSpan.textContent = formatCurrency(data.monto_total || 0);

}



function renderEstadoChart(data) {

  const ctx = $("#estadoChart");

  if (!ctx) return;



  const labels = data.map(item => getEstadoLabel(item.estado));

  const values = data.map(item => item.cantidad);



  new Chart(ctx, {

    type: 'pie',

    data: {

      labels: labels,

      datasets: [{

        data: values,

        backgroundColor: [

          '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'

        ]

      }]

    },

    options: {

      responsive: true,

      plugins: {

        legend: {

          position: 'bottom',

        }

      }

    }

  });

}



function renderCentroChart(data) {

  const ctx = $("#centroChart");

  if (!ctx) return;



  const labels = data.map(item => item.centro || 'Sin centro');

  const values = data.map(item => item.cantidad);



  new Chart(ctx, {

    type: 'bar',

    data: {

      labels: labels,

      datasets: [{

        label: 'Solicitudes',

        data: values,

        backgroundColor: '#36A2EB'

      }]

    },

    options: {

      responsive: true,

      scales: {

        y: {

          beginAtZero: true

        }

      }

    }

  });

}



function renderTendenciaChart(data) {

  const ctx = $("#tendenciaChart");

  if (!ctx) return;



  const labels = data.map(item => item.mes);

  const values = data.map(item => item.cantidad);



  new Chart(ctx, {

    type: 'line',

    data: {

      labels: labels,

      datasets: [{

        label: 'Solicitudes',

        data: values,

        borderColor: '#FF6384',

        backgroundColor: 'rgba(255, 99, 132, 0.2)',

        tension: 0.1

      }]

    },

    options: {

      responsive: true,

      scales: {

        y: {

          beginAtZero: true

        }

      }

    }

  });

}



async function generarReporte() {

  const tipo = $("#reporteTipo")?.value || "solicitudes";

  const formato = $("#reporteFormato")?.value || "excel";

  const fechaDesde = $("#reporteFechaDesde")?.value || "";

  const fechaHasta = $("#reporteFechaHasta")?.value || "";



  try {

    const params = new URLSearchParams({

      tipo,

      formato,

      fecha_desde: fechaDesde,

      fecha_hasta: fechaHasta

    });



    // Crear un enlace temporal para descargar

    const link = document.createElement('a');

    link.href = `${API}/reportes/exportar?${params}`;

    link.download = `reporte.${formato}`;

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);



    toast("Reporte generado exitosamente", true);

  } catch (err) {

    console.error(err);

    toast("Error al generar el reporte");

  }

}



// InicializaciÃ³n de la pÃ¡gina de reportes

function initReportesPage() {

  loadReportesEstadisticas();



  // Configurar botones

  const generarBtn = $("#generarReporteBtn");

  if (generarBtn) {

    generarBtn.addEventListener("click", generarReporte);

  }



  const exportarBtn = $("#exportarDatosBtn");

  if (exportarBtn) {

    exportarBtn.addEventListener("click", () => {

      // Por ahora mismo que generar reporte

      generarReporte();

    });

  }
}

import { AuthAPI } from './api_client.js';
const logoutBtn = document.querySelector('#btn-logout');
if (logoutBtn) logoutBtn.addEventListener('click', async () => { await AuthAPI.logout(); location.href = '/index.html'; });

// Integrar boot.js
import { ensureRole } from './auth_roles.js';

(function(){
   window.__boot_ok = true;
   setTimeout(function(){
     if (!window.__app_bootstrapped) {
       var box = document.createElement('div');
       box.style = 'position:fixed;left:0;right:0;bottom:0;background:#300;color:#fff;padding:8px;font:12px/1.4 monospace;z-index:99999';
       box.textContent = 'Fallo al cargar app.js. Revisa la consola por errores de sintaxis.';
       document.body.appendChild(box);
     }
   }, 1000);
 })();
document.addEventListener('DOMContentLoaded', async () => {
  if (window.initAuthPage) window.initAuthPage();
  try {
    const user = await ensureRole(); // solo valida sesión
    document.querySelectorAll('[data-role]').forEach(el => {
      const needed = el.dataset.role.split(',').map(s=>s.trim());
      const ok = user.roles?.some(r => needed.includes(r));
      if (!ok) el.style.display = 'none';
    });
  } catch { /* ya redirige ensureRole si falla */ }
});

