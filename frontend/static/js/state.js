/* Minimal global state + hash router (kept dependency-free on purpose). */
const State = {
  user: null,           // {id, email, name, is_beginner}
  route: "dashboard",
  toastTimer: null,
};

function isAuthed() { return !!Api.token(); }

function navigate(route) {
  window.location.hash = `#/${route}`;
}

function currentRoute() {
  const hash = window.location.hash.replace(/^#\//, "");
  return hash || (isAuthed() ? "dashboard" : "landing");
}

function toast(message) {
  let el = document.getElementById("global-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "global-toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(State.toastTimer);
  State.toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

function fmtMoney(rupees) {
  const n = Number(rupees) || 0;
  const sign = n < 0 ? "-" : "";
  return sign + "₹" + Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmtDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

const CATEGORY_ICONS = {
  Food: "receipt", Shopping: "receipt", Home: "grid", Transport: "arrow", Bills: "receipt",
  Education: "book", Health: "heart", Entertainment: "chart", Recharge: "receipt",
  Income: "chart", Salary: "chart", Freelance: "pencil", Business: "grid", Investment: "chart", Bonus: "chart", Interest: "chart", Refund: "arrow", Gift: "target", "Other Income": "chart", Other: "receipt",
};
function categoryIcon(cat) { return typeof icon === "function" ? icon(CATEGORY_ICONS[cat] || "receipt", 16, "category-icon") : ""; }
