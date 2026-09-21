/* Reusable render helpers. Everything returns an HTML string or DOM node. */

const ICON_PATHS = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  receipt: '<path d="M6 3h12a2 2 0 0 1 2 2v16l-4-2-4 2-4-2-4 2V5a2 2 0 0 1 2-2Z"/><path d="M8 8h8M8 12h8"/>',
  upload: '<path d="M12 16V4m0 0L8 8m4-4 4 4"/><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
  calendar: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  heart: '<path d="M20.8 8.8c0 5.4-8.8 10.2-8.8 10.2S3.2 14.2 3.2 8.8A4.8 4.8 0 0 1 12 6a4.8 4.8 0 0 1 8.8 2.8Z"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M8 9h8M8 13h8M8 17h5"/>',
  chat: '<path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.6 8.6 0 0 1-3.5-.7L4 20l1.5-3.5A7.3 7.3 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5v-12Z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20"/>',
  chart: '<path d="M4 19V5M4 19h16"/><path d="m7 15 4-5 3 3 4-6"/>',
  settings: '<path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"/><path d="m19.4 15 .1.1-1.7 2.9-.1-.1a2 2 0 0 0-2.1-.2l-.5.3a2 2 0 0 0-1 1.8V20h-3.4v-.2a2 2 0 0 0-1-1.8l-.5-.3a2 2 0 0 0-2.1.2l-.1.1-1.7-2.9.1-.1a2 2 0 0 0 .7-2v-.6a2 2 0 0 0-.7-2l-.1-.1 1.7-2.9.1.1a2 2 0 0 0 2.1.2l.5-.3a2 2 0 0 0 1-1.8V5h3.4v.2a2 2 0 0 0 1 1.8l.5.3a2 2 0 0 0 2.1-.2l.1-.1 1.7 2.9-.1.1a2 2 0 0 0-.7 2v.6a2 2 0 0 0 .7 2Z"/>',
  file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  pencil: '<path d="m4 16.5-.8 4.3 4.3-.8L18.8 8.7a2.8 2.8 0 0 0-4-4L4 16.5Z"/><path d="m13.5 6.5 4 4"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.8 8.2-2.2 5.4-5.4 2.2 2.2-5.4 5.4-2.2Z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  logo: '<path d="M4 19 12 3l8 16-4-2-4 2-4-2-4 2Z"/><path d="M9 12h6"/>',
};
function icon(name, size=20, cls="") { return `<svg class="ui-icon ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name] || ICON_PATHS.grid}</svg>`; }

const NAV_ITEMS_BASE = [
  { route: "dashboard", label: "Dashboard", icon: "grid" },
  { route: "transactions", label: "Transactions", icon: "receipt" },
  { route: "upload", label: "Upload", icon: "upload" },
  { route: "goals", label: "Goals", icon: "target" },
  { route: "saving-plan", label: "Saving Plan", icon: "calendar" },
  { route: "health", label: "Financial Health", icon: "heart" },
  { route: "quiz", label: "Financial Quiz", icon: "clipboard" },
  { route: "coach", label: "AI Money Coach", icon: "chat" },
  { route: "learn", label: "Learn Money", icon: "book" },
  { route: "simulator", label: "Simulator", icon: "chart" },
  { route: "settings", label: "Settings", icon: "settings" },
];

/* Admin nav item only shown to admin-role users - route itself is also
   guarded in app.js so a non-admin can't reach it by typing the hash. */
function getNavItems() {
  if (State.user && State.user.role === "admin") {
    return [...NAV_ITEMS_BASE, { route: "admin", label: "Admin", icon: "settings" }];
  }
  return NAV_ITEMS_BASE;
}

function renderShell(route, contentHtml) {
  const NAV_ITEMS = getNavItems();
  const navHtml = NAV_ITEMS.map(item => `
    <a class="nav-item ${item.route === route ? "active" : ""}" href="#/${item.route}">
      <span class="nav-icon">${icon(item.icon, 17)}</span><span>${item.label}</span>
    </a>`).join("");

  return `
  <div class="app-shell">
    <nav class="sidebar">
      <div class="brand"><span class="brand-mark">${icon("logo", 24)}</span><span class="brand-name">Finora</span></div>
      ${navHtml}
      <div class="nav-spacer"></div>
      <div class="nav-user">${icon("logo", 14)} <span>Hi, ${State.user ? escapeHtml(State.user.name || "there") : "there"}</span></div>
    </nav>
    <div class="main">
      <div class="topbar">
        <div class="row"><span class="brand-mark">${icon("logo", 22)}</span><strong>Finora</strong></div>
        <select class="input" style="width:auto" onchange="navigate(this.value)">
          ${NAV_ITEMS.map(i => `<option value="${i.route}" ${i.route === route ? "selected" : ""}>${i.label}</option>`).join("")}
        </select>
      </div>
      <div class="content" id="route-content">${contentHtml}</div>
    </div>
  </div>`;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function card(innerHtml, extraClass = "") {
  return `<div class="card ${extraClass}">${innerHtml}</div>`;
}

function statCard(eyebrow, valueHtml, subtitle = "", badge = "") {
  return card(`
    <div class="eyebrow">${eyebrow}</div>
    <div class="big-number" style="margin-top:6px;">${valueHtml}</div>
    ${subtitle ? `<div class="subtle" style="margin-top:6px;">${subtitle}</div>` : ""}
    ${badge}
  `);
}

function badge(text, type = "accent") {
  return `<span class="badge badge-${type}">${text}</span>`;
}

function emptyState(iconValue, title, subtitle, actionHtml = "") {
  const renderedIcon = typeof iconValue === "string" && iconValue.includes("<svg") ? iconValue : icon("grid", 28);
  return `<div class="empty-state">
    <div class="empty-icon">${renderedIcon}</div>
    <h3>${title}</h3>
    <p class="subtle" style="margin-top:6px;">${subtitle}</p>
    ${actionHtml ? `<div style="margin-top:16px;">${actionHtml}</div>` : ""}
  </div>`;
}

/* Simple modal system */
function openModal(titleHtml, bodyHtml) {
  closeModal();
  const overlay = document.createElement("div");
  overlay.id = "modal-overlay";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(16,25,46,0.45);display:flex;align-items:center;justify-content:center;z-index:200;padding:16px;";
  overlay.innerHTML = `
    <div class="card" style="max-width:480px;width:100%;max-height:88vh;overflow-y:auto;">
      <div class="row-between" style="margin-bottom:16px;">
        <h3>${titleHtml}</h3>
        <button class="btn btn-ghost btn-sm" onclick="closeModal()">X</button>
      </div>
      <div>${bodyHtml}</div>
    </div>`;
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
}
function closeModal() {
  const el = document.getElementById("modal-overlay");
  if (el) el.remove();
}
