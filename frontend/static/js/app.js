/* Route table. Standalone pages render full-screen (no sidebar); app pages render inside the shell. */
const STANDALONE_ROUTES = new Set(["landing", "login", "register", "onboarding", "upload-onboard", "manual-onboard", "beginner-onboard"]);

const PAGE_RENDERERS = {
  landing: renderLanding,
  login: renderLogin,
  register: renderRegister,
  onboarding: renderOnboarding,
  "upload-onboard": renderUploadOnboard,
  "manual-onboard": renderManualOnboard,
  "beginner-onboard": renderBeginnerOnboard,
  dashboard: renderDashboard,
  transactions: renderTransactions,
  upload: renderUpload,
  goals: renderGoals,
  "saving-plan": renderSavingPlan,
  health: renderHealth,
  quiz: renderQuiz,
  coach: renderCoach,
  learn: renderLearn,
  simulator: renderSimulator,
  settings: renderSettings,
  admin: renderAdmin,
};

const root = document.getElementById("root");

async function loadCurrentUser() {
  if (!isAuthed()) { State.user = null; return; }
  try {
    const res = await Api.get("/auth/me");
    State.user = res.data;
  } catch (e) {
    Api.clearToken();
    State.user = null;
  }
}

async function render() {
  const route = currentRoute();

  // Auth gating
  if (!isAuthed() && !STANDALONE_ROUTES.has(route)) {
    navigate("landing");
    return render();
  }
  if (isAuthed() && (route === "landing" || route === "login" || route === "register")) {
    navigate("dashboard");
    return render();
  }
  // Admin route is for admin-role users only; everyone else bounces to dashboard
  // (the API would also reject them, but this avoids the generic error screen).
  if (route === "admin" && !(State.user && State.user.role === "admin")) {
    navigate("dashboard");
    return render();
  }

  const renderer = PAGE_RENDERERS[route] || renderLanding;

  try {
    if (STANDALONE_ROUTES.has(route)) {
      const html = await renderer();
      root.innerHTML = html;
    } else {
      // Render shell with a lightweight loading state first for snappy perceived performance,
      // then swap in the real content once data resolves.
      root.innerHTML = renderShell(route, `<div class="subtle">Loading...</div>`);
      const html = await renderer();
      const contentEl = document.getElementById("route-content");
      if (contentEl) contentEl.innerHTML = html;
    }
  } catch (err) {
    if (err.status === 401) {
      Api.clearToken();
      navigate("landing");
      return render();
    }
    root.innerHTML = `<div style="padding:40px;text-align:center;">
      <p>Something went wrong loading this page.</p>
      <p class="subtle" style="margin-top:8px;">${escapeHtml(err.message)}</p>
      <button class="btn" style="margin-top:16px;" onclick="render()">Retry</button>
    </div>`;
  }
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", async () => {
  await loadCurrentUser();
  await render();
});
