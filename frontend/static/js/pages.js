/* ---------------- Shared helpers ---------------- */

// Return a greeting based on the user's local browser time. Keeping this
// client-side means it follows the user's actual timezone and changes
// automatically without any backend dependency.
function getTimeGreeting(now = new Date()) {
  const hour = now.getHours();
  if (hour >= 5 && hour < 12) return "Good Morning";
  if (hour >= 12 && hour < 17) return "Good Afternoon";
  if (hour >= 17 && hour < 21) return "Good Evening";
  return "Good Night";
}

/* ---------------- Shared: quick add transaction ---------------- */

const EXPENSE_CATEGORY_OPTIONS = ["Food", "Shopping", "Home", "Transport", "Bills", "Education", "Health", "Entertainment", "Recharge", "Other"];
const INCOME_SOURCE_OPTIONS = ["Salary", "Freelance", "Business", "Investment", "Bonus", "Interest", "Refund", "Gift", "Other Income"];
const CATEGORY_OPTIONS = [...EXPENSE_CATEGORY_OPTIONS, "Income"];

function transactionCategoryOptions(type, selected = "") {
  const options = type === "income" ? INCOME_SOURCE_OPTIONS : EXPENSE_CATEGORY_OPTIONS;
  return options.map(c => `<option value="${c}" ${selected === c ? "selected" : ""}>${categoryIcon(c)} ${c}</option>`).join("");
}

function quickAddFormHtml(initialType = "expense") {
  const today = new Date().toISOString().slice(0, 10);
  const type = initialType === "income" ? "income" : "expense";
  return `
  <form id="quick-add-form">
    <div class="transaction-type-toggle" role="tablist" aria-label="Transaction type">
      <button type="button" class="type-toggle ${type === "expense" ? "active" : ""}" data-type="expense" onclick="setQuickAddType('expense')" id="qa-btn-expense">Expense</button>
      <button type="button" class="type-toggle ${type === "income" ? "active" : ""}" data-type="income" onclick="setQuickAddType('income')" id="qa-btn-income">Income</button>
    </div>
    <input type="hidden" id="qa-type" value="${type}">
    <div class="field">
      <label class="field-label">Amount (₹)</label>
      <input class="input" type="number" min="0.01" step="0.01" id="qa-amount" required placeholder="e.g. ${type === "income" ? "45000" : "500"}">
    </div>
    <div class="field">
      <label class="field-label" id="qa-category-label">${type === "income" ? "Income source" : "Expense category"}</label>
      <select class="input" id="qa-category">${transactionCategoryOptions(type)}</select>
    </div>
    <div class="field">
      <label class="field-label">Date</label>
      <input class="input" type="date" id="qa-date" value="${today}" required>
    </div>
    <div class="field">
      <label class="field-label">${type === "income" ? "Note (optional)" : "Description (optional)"}</label>
      <input class="input" type="text" id="qa-desc" placeholder="e.g. ${type === "income" ? "August salary" : "Lunch with friends"}">
    </div>
    <button class="btn btn-block" type="submit" id="qa-submit">${type === "income" ? "Add income" : "Add expense"}</button>
  </form>`;
}

function setQuickAddType(type) {
  const hidden = document.getElementById("qa-type");
  const category = document.getElementById("qa-category");
  if (!hidden || !category) return;
  hidden.value = type;
  document.getElementById("qa-btn-expense").className = `type-toggle ${type === "expense" ? "active" : ""}`;
  document.getElementById("qa-btn-income").className = `type-toggle ${type === "income" ? "active" : ""}`;
  category.innerHTML = transactionCategoryOptions(type);
  document.getElementById("qa-category-label").textContent = type === "income" ? "Income source" : "Expense category";
  document.getElementById("qa-desc").placeholder = type === "income" ? "e.g. August salary" : "e.g. Lunch with friends";
  document.getElementById("qa-submit").textContent = type === "income" ? "Add income" : "Add expense";
}

async function handleQuickAddSubmit(e, onSuccess) {
  const amount = Number(document.getElementById("qa-amount").value);
  const category = document.getElementById("qa-category").value;
  const date = document.getElementById("qa-date").value;
  const description = document.getElementById("qa-desc").value.trim();
  const type = document.getElementById("qa-type").value;

  try {
    await Api.post("/transactions", {
      date, merchant: description, description, amount_rupees: amount, type,
      category: type === "income" ? category : category,
    });
    document.getElementById("quick-add-form").reset();
    setQuickAddType("expense");
    document.getElementById("qa-date").value = new Date().toISOString().slice(0, 10);
    onSuccess && onSuccess();
  } catch (err) { toast(err.message); }
}

/* Natural language quick entry: "Spent 250 on lunch" */
function nlEntryFormHtml() {
  return `
  <form id="nl-entry-form" class="row" style="gap:8px;">
    <input class="input" type="text" id="nl-text" placeholder="Try: Spent 250 on lunch" style="flex:1;">
    <button class="btn" type="submit">Parse</button>
  </form>
  <div id="nl-preview" style="margin-top:12px;"></div>`;
}

function attachNlEntryHandler(onCommitted) {
  const form = document.getElementById("nl-entry-form");
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = document.getElementById("nl-text").value.trim();
    if (!text) return;
    try {
      const res = await Api.post("/transactions/parse-natural-language", { text });
      const preview = document.getElementById("nl-preview");
      if (!res.meta.parsed) {
        preview.innerHTML = `<p class="subtle">${res.meta.message}</p>`;
        return;
      }
      const d = res.data;
      preview.innerHTML = card(`
        <div class="row-between">
          <div>
            <div><strong>${categoryIcon(d.category)} ${d.category}</strong> - ${fmtMoney(d.amount_rupees)} (${d.type})</div>
            <div class="subtle" style="margin-top:4px;">${escapeHtml(d.description)} - ${d.date}</div>
          </div>
          <button class="btn btn-sm" id="nl-confirm-btn">Add this</button>
        </div>`);
      document.getElementById("nl-confirm-btn").addEventListener("click", async () => {
        try {
          await Api.post("/transactions", {
            date: d.date, merchant: d.description, description: d.description,
            amount_rupees: d.amount_rupees, type: d.type, category: d.category,
          });
          document.getElementById("nl-text").value = "";
          preview.innerHTML = "";
          toast("Added!");
          onCommitted && onCommitted();
        } catch (err) { toast(err.message); }
      });
    } catch (err) { toast(err.message); }
  });
}

/* ---------------- Shared: upload zones (PDF / statement photo / CSV) ---------------- */

function uploadZonesHtml(context) {
  return `
  <div class="stack" style="margin-top:16px;">
    <div class="card">
      <div class="row"><span style="font-size:20px;">${icon("file",18)}</span><strong>Bank statement PDF</strong></div>
      <p class="subtle" style="margin-top:6px;">Upload a bank statement PDF. We extract transactions for you to review before anything is saved.</p>
      <input type="file" accept="application/pdf,.pdf" id="statement-pdf-input-${context}" style="margin-top:10px;">
      <input type="password" id="statement-pdf-password-${context}" class="input" placeholder="PDF password (only if protected)" autocomplete="off" style="margin-top:10px;">
    </div>
    <div class="card">
      <div class="row"><span style="font-size:20px;">${icon("file",18)}</span><strong>Photo of a statement</strong></div>
      <p class="subtle" style="margin-top:6px;">Upload a clear JPG, JPEG, PNG or WebP photo of your statement. OCR extracts transactions for review.</p>
      <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" capture="environment" id="statement-photo-input-${context}" style="margin-top:10px;">
    </div>
    <div class="card">
      <div class="row"><span style="font-size:20px;">${icon("chart",18)}</span><strong>CSV bank export</strong></div>
      <p class="subtle" style="margin-top:6px;">Upload a .CSV bank export. Other file extensions are rejected.</p>
      <input type="file" accept=".csv,text/csv,application/csv" id="csv-input-${context}" style="margin-top:10px;">
    </div>
  </div>
  <div id="upload-status-${context}" style="margin-top:16px;"></div>
  <div id="review-table-${context}" style="margin-top:16px;"></div>`;
}

function validateUploadFile(file, allowedExtensions, label) {
  const name = (file?.name || "").toLowerCase();
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  if (!allowedExtensions.includes(ext)) {
    throw new Error(`${label} must be ${allowedExtensions.join(", ")} only. You selected: ${ext || "a file without an extension"}.`);
  }
  return true;
}

function attachUploadHandlers(context) {
  const statusEl = () => document.getElementById(`upload-status-${context}`);
  const reviewEl = () => document.getElementById(`review-table-${context}`);

  const pdfInput = document.getElementById(`statement-pdf-input-${context}`);
  if (pdfInput) pdfInput.addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try { validateUploadFile(file, [".pdf"], "Bank statement PDF"); }
    catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; e.target.value = ""; return; }
    if (file.size > 20 * 1024 * 1024) { statusEl().innerHTML = `<p class="subtle">PDF is too large. Please choose a file under 20MB.</p>`; e.target.value = ""; return; }
    statusEl().innerHTML = `<p class="subtle">Reading your bank statement PDF... this can take a few seconds.</p>`;
    try {
      const password = document.getElementById(`statement-pdf-password-${context}`)?.value || "";
      const res = await Api.upload("/uploads/statement-pdf", file, "file", { password });
      if (res.meta.status === "ocr_unavailable") { statusEl().innerHTML = `<p class="subtle">${escapeHtml(res.meta.message)}</p>`; return; }
      if (res.meta.status === "no_rows_found") { statusEl().innerHTML = `<p class="subtle">The PDF was opened, but no transactions were detected. Try another statement PDF or CSV export.</p>`; return; }
      const mode = res.meta.extraction_mode === "ocr_fallback" ? "scanned PDF OCR" : "PDF text";
      statusEl().innerHTML = `<p class="subtle">Found ${res.meta.row_count} transaction${res.meta.row_count === 1 ? "" : "s"} from ${mode}. Please review them below.</p>`;
      renderReviewTable(reviewEl(), res.data.rows, context);
    } catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; }
  });

  const statementInput = document.getElementById(`statement-photo-input-${context}`);
  if (statementInput) statementInput.addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try { validateUploadFile(file, [".jpg", ".jpeg", ".png", ".webp"], "Statement photo"); }
    catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; e.target.value = ""; return; }
    if (file.size > 10 * 1024 * 1024) { statusEl().innerHTML = `<p class="subtle">Statement photo is too large. Please choose an image under 10MB.</p>`; e.target.value = ""; return; }
    statusEl().innerHTML = `<p class="subtle">Reading your statement photo with OCR... this can take a few seconds.</p>`;
    try {
      const res = await Api.upload("/uploads/statement-photo", file);
      if (res.meta.status === "ocr_unavailable") { statusEl().innerHTML = `<p class="subtle">${escapeHtml(res.meta.message)}</p>`; return; }
      if (res.meta.status === "no_rows_found") { statusEl().innerHTML = `<p class="subtle">The photo was read, but no transactions were detected. Use a clearer photo with the date, description and amount columns visible.</p>`; return; }
      statusEl().innerHTML = `<p class="subtle">Found ${res.meta.row_count} transaction${res.meta.row_count === 1 ? "" : "s"} from statement photo OCR. Please review them below.</p>`;
      renderReviewTable(reviewEl(), res.data.rows, context);
    } catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; }
  });

  const csvInput = document.getElementById(`csv-input-${context}`);
  if (csvInput) csvInput.addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    try { validateUploadFile(file, [".csv"], "CSV bank export"); }
    catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; e.target.value = ""; return; }
    if (file.size > 10 * 1024 * 1024) { statusEl().innerHTML = `<p class="subtle">CSV is too large. Please choose a file under 10MB.</p>`; e.target.value = ""; return; }
    statusEl().innerHTML = `<p class="subtle">Reading your CSV...</p>`;
    try {
      const res = await Api.upload("/transactions/upload-csv", file);
      statusEl().innerHTML = `<p class="subtle">Found ${res.data.stats.imported} rows (${res.data.stats.failed} skipped).</p>`;
      renderReviewTable(reviewEl(), res.data.rows, context);
    } catch (err) { statusEl().innerHTML = `<p class="subtle">${escapeHtml(err.message)}</p>`; }
  });
}

let _reviewRows = [];

function renderReviewTable(container, rows, context) {
  _reviewRows = rows.map((r, i) => ({ ...r, _id: i }));
  if (!_reviewRows.length) {
    container.innerHTML = card(emptyState(icon("grid",24), "No transactions found", "Try a clearer photo, or add transactions manually."));
    return;
  }
  container.innerHTML = card(`
    <div class="row-between" style="margin-bottom:10px;">
      <strong>Check your transactions</strong>
      <span class="muted">${_reviewRows.length} found</span>
    </div>
    <div style="overflow-x:auto;">
    <table class="txn-table">
      <thead><tr><th>Date</th><th>Merchant</th><th>Amount</th><th>Type</th><th>Category</th><th></th></tr></thead>
      <tbody id="review-tbody-${context}">
        ${_reviewRows.map(r => reviewRowHtml(r, context)).join("")}
      </tbody>
    </table>
    </div>
    <button class="btn btn-block" style="margin-top:14px;" onclick="commitReviewRows('${context}')">Confirm & add all</button>
  `);
}

function reviewRowHtml(r, context) {
  return `<tr data-id="${r._id}">
    <td><input class="input" style="padding:6px 8px;" type="date" value="${r.date}" onchange="updateReviewRow(${r._id},'date',this.value)"></td>
    <td><input class="input" style="padding:6px 8px;min-width:120px;" type="text" value="${escapeHtml(r.merchant || r.description || "")}" onchange="updateReviewRow(${r._id},'merchant',this.value)"></td>
    <td><input class="input" style="padding:6px 8px;width:90px;" type="number" step="0.01" value="${r.amount_rupees ?? ""}" onchange="updateReviewRow(${r._id},'amount_rupees',this.value)"></td>
    <td>
      <select class="input" style="padding:6px 8px;" onchange="updateReviewRow(${r._id},'type',this.value)">
        <option value="expense" ${r.type === "expense" ? "selected" : ""}>Expense</option>
        <option value="income" ${r.type === "income" ? "selected" : ""}>Income</option>
      </select>
    </td>
    <td>
      <select class="input" style="padding:6px 8px;" onchange="updateReviewRow(${r._id},'category',this.value)">
        ${transactionCategoryOptions(r.type, r.category)}
      </select>
    </td>
    <td><button class="btn btn-ghost btn-sm" onclick="removeReviewRow(${r._id},'${context}')">X</button></td>
  </tr>`;
}

function updateReviewRow(id, field, value) {
  const row = _reviewRows.find(r => r._id === id);
  if (row) row[field] = value;
}
function removeReviewRow(id, context) {
  _reviewRows = _reviewRows.filter(r => r._id !== id);
  const tbody = document.getElementById(`review-tbody-${context}`);
  if (tbody) tbody.innerHTML = _reviewRows.map(r => reviewRowHtml(r, context)).join("");
}
async function commitReviewRows(context) {
  if (!_reviewRows.length) return;
  try {
    const res = await Api.post("/transactions/bulk-confirm", _reviewRows.map(r => ({
      date: r.date, merchant: r.merchant || r.description, description: r.description || r.merchant,
      amount_rupees: r.amount_rupees, type: r.type, category: r.category,
      category_source: r.category_source || "manual", confidence: r.confidence || 1.0, source: "manual",
    })));
    toast(`Added ${res.data.imported} transactions (${res.data.duplicates} were duplicates).`);
    document.getElementById(`review-table-${context}`).innerHTML = "";
    _reviewRows = [];
  } catch (err) { toast(err.message); }
}

/* ---------------- Financial Quiz (beginner starting-score) ---------------- */

let _quizAnswers = {};
let _quizResult = null;

async function renderQuiz() {
  _quizResult = null;
  _quizAnswers = {};

  let questions;
  try {
    const res = await Api.get("/profile/quiz");
    questions = res.data;
  } catch (err) {
    // Matches the app-wide error pattern used elsewhere (e.g. renderHealth
    // relies on the top-level render() catch); here we handle it locally too
    // so a failed GET doesn't drop the user out of the page entirely.
    return `
      <h1>Financial Quiz</h1>
      <div class="card" style="margin-top:20px;">
        ${emptyState("WARNING", "Couldn't load the quiz", escapeHtml(err.message), `<button class="btn" onclick="render()">Retry</button>`)}
      </div>`;
  }

  if (!questions || questions.length === 0) {
    return `
      <h1>Financial Quiz</h1>
      <div class="card" style="margin-top:20px;">
        ${emptyState(icon("clipboard",24), "No quiz questions available right now", "Please check back later.")}
      </div>`;
  }

  setTimeout(() => attachQuizHandlers(), 0);

  return `
    <h1>Financial Quiz</h1>
    <p class="subtle" style="margin-top:6px;">A few quick yes/no questions to get a starting financial picture. There are no wrong answers - an estimate is completely okay.</p>
    <div class="card" style="margin-top:20px;">
      <div id="quiz-form-area">
        ${quizQuestionsHtml(questions)}
        <div id="quiz-validation-msg" class="subtle" style="margin-top:10px;"></div>
        <button class="btn btn-block" id="quiz-submit-btn" style="margin-top:16px;" disabled>Answer all questions to see your score</button>
      </div>
      <div id="quiz-result-area"></div>
    </div>
  `;
}

function quizQuestionsHtml(questions) {
  return questions.map(q => `
    <div class="quiz-question" data-qid="${q.id}" style="padding:14px 0;border-top:1px solid var(--border);">
      <p style="margin-bottom:10px;">${escapeHtml(q.text)}</p>
      <div class="row" style="gap:8px;">
        <button type="button" class="btn btn-ghost btn-sm quiz-answer-btn" data-qid="${q.id}" data-value="true">Yes</button>
        <button type="button" class="btn btn-ghost btn-sm quiz-answer-btn" data-qid="${q.id}" data-value="false">No</button>
      </div>
    </div>
  `).join("");
}

function attachQuizHandlers() {
  const buttons = document.querySelectorAll(".quiz-answer-btn");
  const totalQuestions = document.querySelectorAll(".quiz-question").length;
  const submitBtn = document.getElementById("quiz-submit-btn");

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      const qid = btn.dataset.qid;
      const value = btn.dataset.value === "true";
      _quizAnswers[qid] = value;

      // Highlight the selected option, un-highlight its sibling
      const question = btn.closest(".quiz-question");
      question.querySelectorAll(".quiz-answer-btn").forEach(b => b.className = "btn btn-ghost btn-sm quiz-answer-btn");
      btn.className = "btn btn-sm quiz-answer-btn";

      const answeredCount = Object.keys(_quizAnswers).length;
      if (answeredCount >= totalQuestions) {
        submitBtn.disabled = false;
        submitBtn.textContent = "See my starting score";
        document.getElementById("quiz-validation-msg").textContent = "";
      } else {
        submitBtn.disabled = true;
        submitBtn.textContent = `Answer all questions to see your score (${answeredCount}/${totalQuestions})`;
      }
    });
  });

  submitBtn.addEventListener("click", async () => {
    if (Object.keys(_quizAnswers).length < totalQuestions) {
      document.getElementById("quiz-validation-msg").textContent = "Please answer every question before submitting.";
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "Scoring...";
    document.getElementById("quiz-validation-msg").textContent = "";

    try {
      const res = await Api.post("/profile/quiz", _quizAnswers);
      _quizResult = res.data;
      renderQuizResult();
    } catch (err) {
      document.getElementById("quiz-validation-msg").innerHTML =
        `<span style="color:var(--red,#dc2626);">Couldn't score your quiz: ${escapeHtml(err.message)}. Your answers are saved - try again.</span>`;
      submitBtn.disabled = false;
      submitBtn.textContent = "See my starting score";
    }
  });
}

function renderQuizResult() {
  const r = _quizResult;
  const tier = r.starting_score >= 80 ? ["Excellent", "green"] : r.starting_score >= 60 ? ["Good", "green"]
    : r.starting_score >= 40 ? ["Needs attention", "amber"] : ["At risk", "red"];

  document.getElementById("quiz-form-area").style.display = "none";
  document.getElementById("quiz-result-area").innerHTML = `
    <div style="text-align:center;padding:16px 0;">
      <div class="big-number">${r.starting_score}/100</div>
      <span class="badge badge-${tier[1]}" style="margin-top:8px;display:inline-block;">${tier[0]}</span>
    </div>
    <div class="stack" style="margin-top:10px;gap:6px;">
      ${r.breakdown.map(b => `
        <div class="row-between" style="font-size:14px;">
          <span>${b.points >= 0 ? "OK" : "WARNING"} ${escapeHtml(b.question)}</span>
          <span class="subtle">${b.points >= 0 ? "+" : ""}${b.points}</span>
        </div>
      `).join("")}
    </div>
    <div class="quiz-next-step" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border);">
      <div class="eyebrow">What this score is for</div>
      <p style="margin-top:5px;">${escapeHtml(r.biggest_opportunity)}</p>
      <p class="subtle" style="margin-top:6px;">Use your result as a starting point - it points you toward the next financial habit to work on.</p>
      <div class="row" style="flex-wrap:wrap;margin-top:12px;">
        <button class="btn" onclick="navigate('${r.starting_score < 60 ? "saving-plan" : "goals"}')">${r.starting_score < 60 ? "Build my saving plan ->" : "Set a money goal ->"}</button>
        <button class="btn btn-secondary" onclick="navigate('learn')">Learn the basics -></button>
      </div>
    </div>
    <button class="btn btn-ghost btn-block" style="margin-top:12px;" onclick="render()">Retake Quiz</button>
  `;
}

/* ---------------- Landing & Auth ---------------- */

function renderLanding() {
  return `
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;">
    <div style="max-width:480px;width:100%;text-align:center;">
      <div class="brand-mark landing-logo">${icon("logo", 40)}</div>
      <h1 style="font-size:30px;">Finora</h1>
      <p class="subtle" style="margin-top:10px;font-size:16px;">
        Understand your money. Plan your goals.<br>Build better financial habits.
      </p>
      <div class="stack" style="margin-top:28px;">
        <button class="btn btn-block" onclick="navigate('register')">Start Free</button>
        <button class="btn btn-ghost btn-block" onclick="navigate('login')">I already have an account</button>
      </div>
      <p class="muted" style="margin-top:28px;">No bank statement required to get started.</p>
    </div>
  </div>`;
}

function renderLogin() {
  setTimeout(() => {
    document.getElementById("login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      const btn = document.getElementById("login-btn");
      btn.disabled = true; btn.textContent = "Signing in...";
      try {
        const res = await Api.post("/auth/login", { email, password });
        Api.setToken(res.data.access_token);
        State.user = { id: res.data.user_id, name: res.data.name, email: res.data.email, is_beginner: res.data.is_beginner };
        navigate(res.data.is_beginner === null ? "onboarding" : "dashboard");
        render();
      } catch (err) {
        toast(err.message);
        btn.disabled = false; btn.textContent = "Log in";
      }
    });
  }, 0);

  return `
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;">
    <div class="card" style="max-width:380px;width:100%;">
      <h2 style="margin-bottom:4px;">Welcome back</h2>
      <p class="subtle" style="margin-bottom:20px;">Log in to see your money.</p>
      <form id="login-form">
        <div class="field">
          <label class="field-label">Email</label>
          <input class="input" type="email" id="login-email" required>
        </div>
        <div class="field">
          <label class="field-label">Password</label>
          <input class="input" type="password" id="login-password" required>
        </div>
        <button class="btn btn-block" id="login-btn" type="submit">Log in</button>
      </form>
      <p class="subtle" style="margin-top:16px;text-align:center;">
        New here? <a href="#/register" style="color:var(--accent);font-weight:600;">Create an account</a>
      </p>
    </div>
  </div>`;
}

/* ---------------- Onboarding: three starting modes ---------------- */

function renderOnboarding() {
  setTimeout(() => {
    const cards = [...document.querySelectorAll(".onboarding-path")];
    const continueBtn = document.getElementById("onboarding-continue");
    let selectedRoute = "";
    cards.forEach(cardEl => cardEl.addEventListener("click", () => {
      cards.forEach(c => c.classList.remove("selected"));
      cardEl.classList.add("selected");
      selectedRoute = cardEl.dataset.route;
      if (continueBtn) { continueBtn.disabled = false; continueBtn.classList.remove("is-disabled"); }
    }));
    if (continueBtn) continueBtn.addEventListener("click", () => { if (selectedRoute) navigate(selectedRoute); });
  }, 0);
  return `
  <main class="onboarding-page">
    <div class="onboarding-shell">
      <header class="onboarding-header">
        <a class="onboarding-brand" href="#/dashboard" aria-label="Finora"><span class="onboarding-logo">${icon("logo", 22)}</span><span>Finora</span></a>
        <div class="onboarding-progress" aria-label="Step 1 of 3"><span class="progress-dot active"></span><span class="progress-line"></span><span class="progress-dot"></span><span class="progress-line"></span><span class="progress-dot"></span></div>
        <span class="onboarding-step">Step 1 of 3</span>
      </header>
      <section class="onboarding-intro">
        <div class="eyebrow onboarding-eyebrow">SET UP YOUR FINANCIAL SPACE</div>
        <h1>How would you like to start?</h1>
        <p>Choose the path that fits you best. You can change or add information later.</p>
      </section>
      <section class="onboarding-grid" aria-label="Starting options">
        <button class="onboarding-path" type="button" data-route="upload-onboard">
          <span class="path-icon">${icon("file", 22)}</span><span class="path-copy"><strong>Analyze statement</strong><span>Import a bank statement and review detected transactions before anything is saved.</span></span><span class="path-arrow">${icon("arrow", 18)}</span>
        </button>
        <button class="onboarding-path" type="button" data-route="manual-onboard">
          <span class="path-icon">${icon("pencil", 22)}</span><span class="path-copy"><strong>Manual input</strong><span>Add income, expenses and goals yourself for a clean starting point.</span></span><span class="path-arrow">${icon("arrow", 18)}</span>
        </button>
        <button class="onboarding-path" type="button" data-route="beginner-onboard">
          <span class="path-icon">${icon("compass", 22)}</span><span class="path-copy"><strong>Guided path</strong><span>Answer a few simple questions and Finora will build your starting picture.</span></span><span class="path-arrow">${icon("arrow", 18)}</span>
        </button>
      </section>
      <div class="onboarding-action"><button class="btn onboarding-continue is-disabled" id="onboarding-continue" type="button" disabled>Continue ${icon("arrow", 17)}</button><a class="onboarding-skip" href="#/dashboard">Skip for now</a></div>
      <footer class="onboarding-footer">Your information stays private and nothing is imported without your review.</footer>
    </div>
  </main>`;
}
function renderUploadOnboard() {
  setTimeout(() => attachUploadHandlers("onboard"), 0);
  return `
  <div style="min-height:100vh;padding:40px 20px;">
    <div style="max-width:520px;margin:0 auto;">
      <h2>Upload your statement</h2>
      <p class="subtle" style="margin-top:6px;">PDF, statement photo, or CSV import is available. You'll review every detected transaction before anything is saved.</p>
      ${uploadZonesHtml("onboard")}
      <p class="muted" style="text-align:center;margin-top:20px;"><a href="#/dashboard" style="color:var(--accent);">Skip and go to dashboard -></a></p>
    </div>
  </div>`;
}

function renderManualOnboard() {
  setTimeout(() => {
    document.getElementById("quick-add-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleQuickAddSubmit(e, () => { toast("Added! Add another or head to your dashboard."); });
    });
  }, 0);
  return `
  <div style="min-height:100vh;padding:40px 20px;">
    <div style="max-width:420px;margin:0 auto;">
      <h2>Add a few transactions</h2>
      <p class="subtle" style="margin-top:6px;">Takes a few seconds each. You can add more anytime.</p>
      <div class="card" style="margin-top:20px;">${quickAddFormHtml()}</div>
      <button class="btn btn-block" style="margin-top:16px;" onclick="navigate('dashboard')">Done - go to dashboard</button>
    </div>
  </div>`;
}

function renderBeginnerOnboard() {
  setTimeout(() => {
    document.getElementById("estimate-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        monthly_income_rupees: Number(document.getElementById("est-income").value || 0),
        fixed_expenses_rupees: Number(document.getElementById("est-fixed").value || 0),
        lifestyle_expenses_rupees: Number(document.getElementById("est-lifestyle").value || 0),
        debt_emi_rupees: Number(document.getElementById("est-debt").value || 0),
        existing_savings_rupees: Number(document.getElementById("est-savings").value || 0),
        emergency_savings_rupees: Number(document.getElementById("est-emergency").value || 0),
      };
      try {
        await Api.post("/profile/estimate", payload);
        toast("Got it - this is just a starting estimate.");
        navigate("dashboard");
        render();
      } catch (err) { toast(err.message); }
    });
  }, 0);

  return `
  <div style="min-height:100vh;padding:40px 20px;">
    <div style="max-width:480px;margin:0 auto;">
      <h2>Let's build a starting picture</h2>
      <p class="subtle" style="margin-top:6px;">Exact numbers aren't required - an estimate is completely okay.</p>
      <form id="estimate-form" class="card" style="margin-top:20px;">
        ${numberField("est-income", "Approximate monthly income", "e.g. 45000")}
        ${numberField("est-fixed", "Fixed expenses (rent, EMI, bills)", "e.g. 15000")}
        ${numberField("est-lifestyle", "Lifestyle expenses (food, shopping, etc.)", "e.g. 12000")}
        ${numberField("est-debt", "Monthly debt / EMI payments", "e.g. 0")}
        ${numberField("est-savings", "Existing savings", "e.g. 20000")}
        ${numberField("est-emergency", "Emergency savings set aside", "e.g. 10000")}
        <button class="btn btn-block" type="submit">See my starting picture</button>
      </form>
    </div>
  </div>`;
}

function numberField(id, label, placeholder) {
  return `<div class="field">
    <label class="field-label">${label}</label>
    <input class="input" type="number" min="0" step="1" id="${id}" placeholder="${placeholder}">
  </div>`;
}

/* ---------------- Dashboard ---------------- */

async function renderDashboard() {
  const [summaryRes, healthRes, txRes, goalsRes, monthlyRes] = await Promise.all([
    Api.get("/analytics/summary"),
    Api.get("/analytics/financial-health"),
    Api.get("/transactions?page=1&page_size=5"),
    Api.get("/goals"),
    Api.get("/analytics/monthly"),
  ]);
  const s = summaryRes.data;
  const h = healthRes.data;
  const recentTxns = txRes.data;
  const goals = goalsRes.data;
  const monthly = monthlyRes.data || [];
  const activeGoal = goals.find(g => !g.achieved);
  if (monthly.length) setTimeout(() => growDashboardChartBars(), 30);

  let goalCardHtml;
  if (activeGoal) {
    let planData = null;
    try { planData = (await Api.get(`/goals/${activeGoal.id}/plan`)).data; } catch (e) { /* ignore */ }
    const progressPct = Math.min(100, Math.round((activeGoal.current_saved_rupees / activeGoal.target_amount_rupees) * 100));
    goalCardHtml = card(`
      <div class="row-between"><div class="eyebrow">Current Goal</div>${statusBadge(planData ? planData.live_status : null)}</div>
      <h3 style="margin-top:6px;">${escapeHtml(activeGoal.name)}</h3>
      <div class="progress-track" style="margin-top:10px;"><div class="progress-fill" style="width:${progressPct}%;"></div></div>
      <div class="row-between" style="margin-top:8px;">
        <span class="subtle">${fmtMoney(activeGoal.current_saved_rupees)} saved</span>
        <span class="subtle">${fmtMoney(activeGoal.target_amount_rupees)} goal</span>
      </div>
      ${planData && planData.required_monthly_rupees !== undefined ? `<p class="subtle" style="margin-top:10px;">Save about <strong>${fmtMoney(planData.required_monthly_rupees)}</strong>/month to hit this by ${activeGoal.target_date}.</p>` : ""}
      <a href="#/goals" style="color:var(--accent);font-weight:600;font-size:14px;display:inline-block;margin-top:10px;">View saving plan -></a>
    `);
  } else {
    goalCardHtml = card(emptyState(icon("target",24), "No goal yet", "Set a goal and we'll tell you exactly how much to save each month.",
      `<button class="btn" onclick="navigate('goals')">Create a goal</button>`));
  }

  return `
    <div class="row-between" style="margin-bottom:20px;">
      <div><h1>Good to see you</h1><p class="subtle" style="margin-top:4px;">Here's where things stand.${s.is_estimate ? ' <span style="color:var(--amber);">(based on your estimate)</span>' : ""}</p></div>
      <div class="row dashboard-actions">
        <button class="btn btn-secondary" onclick="openQuickAddModal('income')">+ Add Income</button>
        <button class="btn" onclick="openQuickAddModal('expense')">+ Add Expense</button>
      </div>
    </div>

    <div class="grid grid-3" style="margin-bottom:16px;">
      ${statCard("Income", fmtMoney(s.total_income_rupees), "All time")}
      ${statCard("Expenses", fmtMoney(s.total_expense_rupees), "All time")}
      ${statCard("Savings", fmtMoney(s.savings_rupees), `${Math.round((s.savings_rate || 0) * 100)}% savings rate`)}
    </div>

    <div class="grid grid-2" style="margin-bottom:16px;align-items:start;">
      ${goalCardHtml}
      ${card(`
        <div class="row-between"><div class="eyebrow">Financial Health</div>${badge(h.tier + " " + h.emoji, healthTierBadgeType(h.tier))}</div>
        <div class="big-number" style="margin-top:6px;">${h.score}/100</div>
        <div class="stack" style="margin-top:10px;gap:6px;">
          ${h.breakdown.slice(0, 3).map(b => `<div class="subtle" style="font-size:13px;">${b.points >= 0 ? icon("check", 14) : icon("target", 14)} ${b.reason}</div>`).join("")}
        </div>
        <a href="#/health" style="color:var(--accent);font-weight:600;font-size:14px;display:inline-block;margin-top:10px;">See full breakdown -></a>
      `)}
    </div>

    ${goals.length > 1 ? `<div class="card" style="margin-bottom:16px;"><div class="row-between"><div><div class="eyebrow">Your goals</div><h3 style="margin-top:4px;">Everything you're saving for</h3></div><a href="#/goals" style="color:var(--accent);font-weight:700;font-size:14px;">Manage all -></a></div><div class="goal-mini-grid" style="margin-top:14px;">${goals.slice(0,4).map(g => { const pct=Math.min(100,Math.round((g.current_saved_rupees/g.target_amount_rupees)*100)); return `<div class="goal-mini"><div class="row-between"><strong>${categoryIcon2emoji(g.category)} ${escapeHtml(g.name)}</strong><span class="muted">${pct}%</span></div><div class="progress-track" style="margin-top:8px;"><div class="progress-fill" style="width:${pct}%;"></div></div><div class="muted" style="margin-top:5px;">${fmtMoney(g.current_saved_rupees)} of ${fmtMoney(g.target_amount_rupees)}</div></div>`; }).join("")}</div></div>` : ""}

    <div class="card" style="margin-bottom:16px;border:1px solid var(--accent);background:var(--accent-bg);">
      <div class="row-between" style="gap:16px;">
        <div>
          <div class="eyebrow">BANK STATEMENT IMPORT</div>
          <h3 style="margin-top:4px;">Import a bank statement PDF</h3>
          <p class="subtle" style="margin-top:6px;">Upload a PDF statement and review detected transactions before anything is saved.</p>
        </div>
        <button class="btn" onclick="navigate('upload')">Import PDF</button>
      </div>
    </div>

    <div class="card dashboard-chart-card" style="margin-bottom:16px;">
      <div class="row-between"><div><div class="eyebrow">Money flow</div><h3 style="margin-top:4px;">Income vs spending</h3></div><span class="muted">Last ${Math.min(6, monthly.length)} months</span></div>
      ${monthly.length ? `<div class="monthly-chart">${monthly.slice(-6).map(m => { const max = Math.max(1, ...monthly.slice(-6).flatMap(x => [Number(x.income_rupees||0),Number(x.expense_rupees||0)])); const inc = Math.max(3, Number(m.income_rupees||0)/max*100); const exp = Math.max(3, Number(m.expense_rupees||0)/max*100); return `<div class="chart-col"><div class="chart-bars"><div class="chart-bar income" style="height:0%" data-h="${inc}" title="Income ${fmtMoney(m.income_rupees)}"></div><div class="chart-bar expense" style="height:0%" data-h="${exp}" title="Expenses ${fmtMoney(m.expense_rupees)}"></div></div><span>${escapeHtml(m.month.slice(5))}</span></div>`; }).join("")}</div><div class="chart-legend"><span><i class="dot income-dot"></i>Income</span><span><i class="dot expense-dot"></i>Expenses</span></div>` : emptyState(icon("chart",18), "Your money flow will appear here", "Add income and expenses to see the pattern over time.")}
    </div>

    <div class="card">
      <div class="row-between" style="margin-bottom:12px;"><strong>Recent transactions</strong><a href="#/transactions" style="color:var(--accent);font-weight:600;font-size:14px;">View all -></a></div>
      ${recentTxns.length ? transactionsTableHtml(recentTxns, true) : emptyState(icon("receipt",24), "No transactions yet", "Add your first one to get started.")}
    </div>

    <div id="quick-add-modal-target"></div>
  `;
}

/* Grows the monthly income/expense bars from 0 to their real height on
   mount instead of snapping straight in - the bars already have a CSS
   height transition (.chart-bar), this just gives it a starting point. */
function growDashboardChartBars() {
  document.querySelectorAll(".chart-bar[data-h]").forEach(bar => {
    bar.style.height = `${bar.dataset.h}%`;
  });
}

function statusBadge(status) {
  const map = {
    ahead: ["Ahead ", "green"], on_track: ["On track ", "accent"],
    slightly_behind: ["Slightly behind ", "amber"], behind: ["Behind ", "red"],
    achieved: ["Achieved ", "green"], deadline_passed: ["Deadline passed", "red"],
  };
  const [text, type] = map[status] || ["", "accent"];
  return text ? badge(text, type) : "";
}
function healthTierBadgeType(tier) {
  if (tier === "Excellent" || tier === "Good") return "green";
  if (tier === "Needs attention") return "amber";
  return "red";
}

let _txnCache = {};

function transactionsTableHtml(txns, showActions = true) {
  txns.forEach(t => { _txnCache[t.id] = t; });
  return `<div style="overflow-x:auto;"><table class="txn-table">
    <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Amount</th>${showActions ? "<th></th>" : ""}</tr></thead>
    <tbody>
      ${txns.map(t => `<tr>
        <td class="muted">${fmtDate(t.date)}</td>
        <td>${escapeHtml(t.merchant || t.description || "-")}</td>
        <td>${categoryIcon(t.category)} ${t.category}</td>
        <td style="color:${t.type === "income" ? "var(--green)" : "var(--text)"};font-weight:600;">
          ${t.type === "income" ? "+" : "-"}${fmtMoney(t.amount_rupees)}
        </td>
        ${showActions ? `<td class="row" style="gap:6px;">
            <button class="btn btn-ghost btn-sm" onclick="openEditTransactionModal(${t.id})">Edit</button>
            <button class="btn btn-ghost btn-sm" onclick="deleteTransaction(${t.id})">Delete</button>
          </td>` : ""}
      </tr>`).join("")}
    </tbody>
  </table></div>`;
}

function openQuickAddModal(initialType = "expense") {
  const isIncome = initialType === "income";
  openModal(isIncome ? "Add Income" : "Add Expense", quickAddFormHtml(initialType));
  document.getElementById("quick-add-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    await handleQuickAddSubmit(e, () => { closeModal(); toast("Added!"); render(); });
  });
}

async function deleteTransaction(id) {
  if (!confirm("Delete this transaction?")) return;
  try { await Api.del(`/transactions/${id}`); toast("Deleted."); render(); }
  catch (err) { toast(err.message); }
}

/* ---------------- Edit transaction ---------------- */
/* Reuses the same field set the quick-add form uses (date, merchant,
   description, amount, type, category) since that's exactly what
   PUT /transactions/{id} accepts - no new fields, no separate system. */

function editTransactionFormHtml(t) {
  return `
  <form id="edit-txn-form">
    <input type="hidden" id="et-id" value="${t.id}">
    <div class="row" style="gap:8px;margin-bottom:14px;">
      <button type="button" class="btn ${t.type === "expense" ? "" : "btn-ghost"} btn-sm" onclick="setEditTxnType('expense')" id="et-btn-expense">Expense</button>
      <button type="button" class="btn ${t.type === "income" ? "" : "btn-ghost"} btn-sm" onclick="setEditTxnType('income')" id="et-btn-income">Income</button>
    </div>
    <input type="hidden" id="et-type" value="${t.type}">
    <div class="field">
      <label class="field-label">Amount (₹)</label>
      <input class="input" type="number" min="0.01" step="0.01" id="et-amount" value="${t.amount_rupees}" required>
    </div>
    <div class="field">
      <label class="field-label" id="et-category-label">${t.type === "income" ? "Income source" : "Expense category"}</label>
      <select class="input" id="et-category">${transactionCategoryOptions(t.type, t.category)}</select>
    </div>
    <div class="field">
      <label class="field-label">Date</label>
      <input class="input" type="date" id="et-date" value="${t.date}" required>
    </div>
    <div class="field">
      <label class="field-label">Merchant</label>
      <input class="input" type="text" id="et-merchant" value="${escapeHtml(t.merchant || "")}">
    </div>
    <div class="field">
      <label class="field-label">Description (optional)</label>
      <input class="input" type="text" id="et-desc" value="${escapeHtml(t.description || "")}">
    </div>
    <div id="edit-txn-error"></div>
    <button class="btn btn-block" type="submit" id="edit-txn-submit-btn">Save changes</button>
  </form>`;
}

function setEditTxnType(type) {
  document.getElementById("et-type").value = type;
  document.getElementById("et-btn-expense").className = type === "expense" ? "btn btn-sm" : "btn btn-ghost btn-sm";
  document.getElementById("et-btn-income").className = type === "income" ? "btn btn-sm" : "btn btn-ghost btn-sm";
  document.getElementById("et-category").innerHTML = transactionCategoryOptions(type);
  document.getElementById("et-category-label").textContent = type === "income" ? "Income source" : "Expense category";
}

function openEditTransactionModal(id) {
  const txn = _txnCache[id];
  if (!txn) { toast("Couldn't find that transaction - try refreshing."); return; }

  openModal("Edit Transaction", editTransactionFormHtml(txn));
  document.getElementById("edit-txn-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("edit-txn-submit-btn");
    const errorEl = document.getElementById("edit-txn-error");
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = "Saving...";
    errorEl.innerHTML = "";

    const payload = {
      date: document.getElementById("et-date").value,
      merchant: document.getElementById("et-merchant").value,
      description: document.getElementById("et-desc").value,
      amount_rupees: Number(document.getElementById("et-amount").value),
      type: document.getElementById("et-type").value,
      category: document.getElementById("et-category").value,
    };

    try {
      await Api.put(`/transactions/${id}`, payload);
      closeModal();
      toast("Transaction updated.");
      render();
    } catch (err) {
      errorEl.innerHTML = `<p class="subtle" style="color:var(--red,#dc2626);margin-top:10px;">Couldn't save changes: ${escapeHtml(err.message)}. Please try again.</p>`;
      btn.disabled = false;
      btn.textContent = originalText;
    }
  });
}

/* ---------------- Transactions ---------------- */

async function renderTransactions(query = {}) {
  const params = new URLSearchParams({ page: 1, page_size: 50, ...query });
  const res = await Api.get(`/transactions?${params.toString()}`);
  const txns = res.data;

  setTimeout(() => {
    document.getElementById("txn-search").addEventListener("input", debounce(async (e) => {
      const html = await renderTransactions({ search: e.target.value });
      document.getElementById("route-content").innerHTML = html;
    }, 350));
    attachNlEntryHandler(() => render());
  }, 0);

  return `
    <div class="row-between" style="margin-bottom:20px;">
      <h1>Transactions</h1>
      <div class="row dashboard-actions">
        <button class="btn btn-secondary" onclick="openQuickAddModal('income')">+ Add Income</button>
        <button class="btn" onclick="openQuickAddModal('expense')">+ Add Expense</button>
      </div>
    </div>
    <div class="card" style="margin-bottom:16px;">
      <div class="eyebrow" style="margin-bottom:8px;">Quick add by typing</div>
      ${nlEntryFormHtml()}
    </div>
    <div class="card">
      <input class="input" id="txn-search" placeholder="Search merchant or description..." style="margin-bottom:16px;">
      ${txns.length ? transactionsTableHtml(txns, true) : emptyState(icon("receipt",24), "No transactions yet", "Add one manually, or upload a statement.")}
    </div>
  `;
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/* ---------------- Upload ---------------- */

function renderUpload() {
  setTimeout(() => { attachUploadHandlers("main"); attachNlEntryHandler(); }, 0);
  return `
    <h1>Add your data</h1>
    <p class="subtle" style="margin-top:6px;">Import a bank statement PDF, statement photo, or CSV bank export, or type a transaction.</p>
    <div class="card" style="margin-top:20px;">
      <div class="eyebrow" style="margin-bottom:8px;">Type it</div>
      ${nlEntryFormHtml()}
    </div>
    <div style="margin-top:16px;">${uploadZonesHtml("main")}</div>
  `;
}

/* ---------------- Goals ---------------- */

async function renderGoals() {
  const res = await Api.get("/goals");
  const goals = Array.isArray(res.data) ? res.data : [];

  const goalCards = await Promise.all(goals.map(async g => {
    let plan = null;
    try { plan = (await Api.get(`/goals/${g.id}/plan`)).data; } catch (e) { /* keep card usable even if plan fails */ }
    return goalDetailCardHtml(g, plan);
  }));

  return `
    <div class="page-hero goal-hero">
      <div><span class="hero-kicker">PLAN WHAT MATTERS</span><h1>Goals</h1><p class="subtle" style="margin-top:6px;">Create as many goals as you need. Keep 3-4 active goals for a balanced plan, or add more when your priorities change.</p></div>
      <div class="hero-orb">${icon("target",24)}</div>
    </div>

    <div class="card" style="margin:20px 0;">
      <div class="row-between" style="margin-bottom:12px;">
        <div><div class="eyebrow">${goals.length ? "Add another goal" : "New goal"}</div><div class="subtle" style="margin-top:4px;">Each goal is saved separately and will appear below.</div></div>
        ${goals.length ? `<span class="badge badge-green">${goals.length} active ${goals.length === 1 ? "goal" : "goals"}</span>` : ""}
      </div>
      <form id="new-goal-form" onsubmit="handleCreateGoal(event)">
        <div class="grid grid-2">
          <div class="field"><label class="field-label">Name</label><input class="input" id="goal-name" placeholder="e.g. Laptop" required></div>
          <div class="field"><label class="field-label">Category</label>
            <select class="input" id="goal-category">
              ${["Laptop", "Phone", "Bike", "Car", "Education", "Travel", "Emergency Fund", "Wedding", "House", "Business", "Custom"].map(c => `<option>${c}</option>`).join("")}
            </select>
          </div>
          <div class="field"><label class="field-label">Target amount (₹)</label><input class="input" type="number" min="1" step="1" id="goal-target" required></div>
          <div class="field"><label class="field-label">Target date</label><input class="input" type="date" id="goal-date" required></div>
          <div class="field"><label class="field-label">Already saved (₹)</label><input class="input" type="number" min="0" step="1" id="goal-saved" value="0"></div>
        </div>
        <button class="btn" type="submit" id="create-goal-btn">${goals.length ? "Add another goal" : "Create goal"}</button>
      </form>
    </div>

    ${goals.length ? `<div class="grid goal-grid">${goalCards.join("")}</div>` : card(emptyState(icon("target",24), "No goals yet", "Create your first goal above."))}
  `;
}

async function handleCreateGoal(e) {
  e.preventDefault();
  const name = document.getElementById("goal-name")?.value.trim();
  const category = document.getElementById("goal-category")?.value;
  const target = Number(document.getElementById("goal-target")?.value);
  const date = document.getElementById("goal-date")?.value;
  const saved = Number(document.getElementById("goal-saved")?.value || 0);
  const btn = document.getElementById("create-goal-btn");

  if (!name || !target || target <= 0 || !date) {
    toast("Please enter a goal name, target amount and target date.");
    return;
  }
  if (saved < 0 || saved > target) {
    toast("Already saved must be between ₹0 and the target amount.");
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = "Creating..."; }
  try {
    await Api.post("/goals", {
      name, category, target_amount_rupees: target, target_date: date, current_saved_rupees: saved,
    });
    toast("Goal created successfully.");
    await render();
  } catch (err) {
    toast(err.message);
    if (btn) { btn.disabled = false; btn.textContent = "Add another goal"; }
  }
}

function goalDetailCardHtml(g, plan) {
  const progressPct = Math.min(100, Math.round((g.current_saved_rupees / g.target_amount_rupees) * 100));
  if (!plan || plan.status === "achieved") {
    return card(`
      <div class="row-between"><h3>${escapeHtml(g.name)}</h3>${badge("Achieved ", "green")}</div>
      <p class="subtle" style="margin-top:6px;">${fmtMoney(g.current_saved_rupees)} of ${fmtMoney(g.target_amount_rupees)} saved.</p>
      <button class="btn btn-ghost btn-sm" style="margin-top:12px;" onclick="deleteGoal(${g.id})">Delete</button>
    `);
  }
  if (plan.status === "deadline_passed") {
    return card(`
      <div class="row-between"><h3>${escapeHtml(g.name)}</h3>${badge("Deadline passed", "red")}</div>
      <p class="subtle" style="margin-top:6px;">${plan.message}</p>
      <button class="btn btn-ghost btn-sm" style="margin-top:12px;" onclick="deleteGoal(${g.id})">Delete</button>
    `);
  }

  const suggestions = plan.suggestions || [];
  return card(`
    <div class="row-between">
      <h3>${categoryIcon2emoji(g.category)} ${escapeHtml(g.name)}</h3>
      ${statusBadge(plan.live_status)}
    </div>
    <div class="progress-track" style="margin-top:10px;"><div class="progress-fill" style="width:${progressPct}%;"></div></div>
    <div class="row-between" style="margin-top:8px;">
      <span class="subtle">${fmtMoney(g.current_saved_rupees)} saved</span>
      <span class="subtle">${fmtMoney(g.target_amount_rupees)} by ${g.target_date}</span>
    </div>
    <p style="margin-top:12px;">You need to save approximately <strong>${fmtMoney(plan.required_monthly_rupees)}</strong> every month (${plan.months_remaining} months left).</p>
    ${plan.shortfall_reason ? `<p class="subtle" style="margin-top:6px;">${plan.shortfall_reason}</p>` : ""}
    ${suggestions.length ? `
      <div style="margin-top:14px;">
        <div class="eyebrow" style="margin-bottom:8px;">Where this could come from</div>
        ${suggestions.map(s => `
          <div class="row-between" style="padding:8px 0;border-top:1px solid var(--border);">
            <span>${categoryIcon(s.category)} ${s.category}</span>
            <span class="subtle">${fmtMoney(s.current_average_rupees)} -> ${fmtMoney(s.suggested_target_rupees)}</span>
            <span class="badge badge-green">Potential -${fmtMoney(s.potential_saving_rupees)}</span>
          </div>`).join("")}
        <p class="muted" style="margin-top:10px;">Potential monthly reduction: ${fmtMoney(plan.potential_total_rupees)}. ${plan.gap_rupees > 0 ? `You'd still need about ${fmtMoney(plan.gap_rupees)} more per month.` : "That could fully cover your target!"}</p>
      </div>` : ""}
    <button class="btn btn-ghost btn-sm" style="margin-top:14px;" onclick="deleteGoal(${g.id})">Delete goal</button>
  `);
}
function categoryIcon2emoji(cat) {
  const map = { Laptop: icon("grid",18), Phone: icon("receipt",18), Bike: icon("arrow",18), Car: icon("arrow",18), Education: icon("book",18), Travel: icon("arrow",18), "Emergency Fund": icon("heart",18), Wedding: icon("target",18), House: icon("grid",18), Business: icon("grid",18), Custom: icon("target",24) };
  return map[cat] || icon("target",24);
}
async function deleteGoal(id) {
  if (!confirm("Delete this goal?")) return;
  try { await Api.del(`/goals/${id}`); toast("Deleted."); render(); } catch (err) { toast(err.message); }
}

/* ---------------- Saving Plan ("Where can I save?") ---------------- */

async function renderSavingPlan() {
  const res = await Api.get("/analytics/save-suggestions");
  const suggestions = res.data;
  const totalLow = suggestions.reduce((n, s) => n + Number(s.potential_saving_low_rupees || 0), 0);
  const totalHigh = suggestions.reduce((n, s) => n + Number(s.potential_saving_high_rupees || 0), 0);
  const grouped = { essential: [], flexible: [], discretionary: [] };
  suggestions.forEach(s => (grouped[s.flexibility] || grouped.discretionary).push(s));
  const meaning = {
    essential: ["Must-have", "Rent, core bills, medicine and other needs. Don't cut these aggressively."],
    flexible: ["Can adjust", "Useful spending you can reduce a little without removing it completely."],
    discretionary: ["Nice-to-have", "Optional spending where a temporary cut can free money for your goals."]
  };
  return `
    <div class="page-hero saving-hero"><div><span class="hero-kicker">MAKE YOUR MONEY WORK</span><h1>Saving Plan</h1><p class="subtle" style="margin-top:6px;">This page turns your spending into simple actions - what to protect, what to adjust, and where you could free up money.</p></div><div class="hero-orb">${icon("chart",18)}</div></div>
    <div class="grid grid-3 saving-summary" style="margin-top:20px;">
      ${statCard("Possible monthly saving", `${fmtMoney(totalLow)}-${fmtMoney(totalHigh)}`, "A practical range, not a promise")}
      ${statCard("Flexible spending", `${grouped.flexible.length} areas`, "Can usually be trimmed gradually")}
      ${statCard("Discretionary spending", `${grouped.discretionary.length} areas`, "Best place to look for quick wins")}
    </div>
    <div class="grid grid-3" style="margin-top:16px;">
      ${Object.entries(meaning).map(([key, v]) => card(`<div class="flexibility-icon">${key === "essential" ? icon("heart",18) : key === "flexible" ? icon("settings",18) : icon("arrow",18)}</div><h3 style="margin-top:10px;">${v[0]}</h3><p class="subtle" style="margin-top:6px;">${v[1]}</p>`)).join("")}
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="row-between"><div><div class="eyebrow">Your action list</div><h3 style="margin-top:4px;">Where can you save?</h3></div><span class="badge badge-accent">Based on your spending</span></div>
      <div class="stack" style="margin-top:14px;">
      ${suggestions.length ? suggestions.map((s, i) => card(`
        <div class="row-between"><div class="row"><span class="rank-pill">${i + 1}</span><div><strong>${categoryIcon(s.category)} ${s.category}</strong><div class="muted">${s.flexibility === "flexible" ? "Adjust, don't eliminate" : s.flexibility === "discretionary" ? "Easy place to create a goal fund" : "Protect this essential"}</div></div></div><span class="badge badge-${s.flexibility === "discretionary" ? "amber" : s.flexibility === "flexible" ? "accent" : "green"}">${s.flexibility}</span></div>
        <div class="mini-bar" style="margin-top:12px;"><div style="width:${Math.min(100, Math.max(8, Number(s.average_monthly_rupees || 0) / Math.max(1, Math.max(...suggestions.map(x => Number(x.average_monthly_rupees || 0)))) * 100))}%"></div></div>
        <div class="row-between" style="margin-top:8px;"><span class="subtle">~${fmtMoney(s.average_monthly_rupees)}/month${s.change_pct ? ` - ${s.change_pct > 0 ? "+" : ""}${s.change_pct}% vs earlier` : ""}</span><strong>Save ${fmtMoney(s.potential_saving_low_rupees)}-${fmtMoney(s.potential_saving_high_rupees)}</strong></div>
      `)).join("") : emptyState(icon("chart",18), "Not enough data yet", "Add a few weeks of transactions and we'll find patterns.")}
      </div>
    </div>
  `;
}

/* ---------------- Financial Health ---------------- */

async function renderHealth() {
  const [healthRes, summaryRes, profileRes] = await Promise.all([
    Api.get("/analytics/financial-health"), Api.get("/analytics/summary"), Api.get("/profile")
  ]);
  const h = healthRes.data, s = summaryRes.data, profile = profileRes.data || {};
  const positive = h.breakdown.filter(b => b.points >= 0).length;
  const scoreAngle = Math.max(0, Math.min(100, Number(h.score || 0))) * 3.6;
  const actions = [];
  if ((s.savings_rate || 0) < 0.1) actions.push([icon("chart",18), "Build a small monthly saving habit", "Start with a fixed amount you can repeat every month.", "saving-plan"]);
  if ((profile.emergency_savings_rupees || 0) <= 0) actions.push([icon("heart",18), "Start your emergency fund", "Aim first for 1 month of essential expenses, then build toward 3-6 months.", "learn"]);
  if ((profile.debt_emi_rupees || 0) > 0) actions.push([icon("chart",18), "Keep EMI pressure visible", "Try to keep loan payments at a manageable share of your income.", "learn"]);
  if (!actions.length) actions.push([icon("arrow",18), "Turn your good score into a goal", "Use Goals to give your monthly surplus a clear purpose.", "goals"]);
  setTimeout(() => animateHealthScore(scoreAngle, Number(h.score || 0)), 20);
  return `
    <div class="page-hero health-hero"><div><span class="hero-kicker">YOUR MONEY CHECK-UP</span><h1>Financial Health <3</h1><p class="subtle" style="margin-top:6px;">A simple score showing what is going well and what could make your finances stronger.</p></div><div class="hero-orb"><3</div></div>
    <div class="health-layout" style="margin-top:20px;">
      <div class="card health-score-card">
        <div class="score-ring" id="health-score-ring" style="--score:0deg"><div><span class="score-number" id="health-score-number">0</span><span class="score-total">/100</span></div></div>
        <h2 style="margin-top:18px;">${h.tier}</h2><p class="subtle" style="margin-top:6px;">${positive}/${h.breakdown.length} areas are currently positive.</p>
        ${h.is_estimate ? `<div class="notice-box" style="margin-top:16px;">${icon("target",18)} Based on your starting estimate. Add real transactions to make this score more accurate.</div>` : ""}
      </div>
      <div class="card">
        <div class="eyebrow">What your score means</div>
        <div class="stack" style="margin-top:12px;gap:10px;">
          ${h.breakdown.map(b => `<div class="health-row"><div><strong>${b.points >= 0 ? "OK" : "WARNING"} ${escapeHtml(b.label)}</strong><p class="muted" style="margin-top:3px;">${escapeHtml(b.reason)}</p></div><span class="badge badge-${b.points >= 0 ? "green" : "amber"}">${b.points >= 0 ? "+" : ""}${b.points}</span></div>`).join("")}
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="eyebrow">Your next best moves</div><h3 style="margin-top:4px;">Improve one thing at a time</h3>
      <div class="grid grid-3" style="margin-top:14px;">${actions.map(a => card(`<div style="font-size:24px;">${a[0]}</div><h3 style="margin-top:8px;font-size:16px;">${a[1]}</h3><p class="subtle" style="margin-top:6px;">${a[2]}</p><button class="btn btn-secondary btn-sm" style="margin-top:12px;" onclick="navigate('${a[3]}')">Take action -></button>`)).join("")}</div>
    </div>
  `;
}

/* Sweeps the health score ring from 0 to its real value and counts the
   number up alongside it, instead of snapping straight to the final state. */
function animateHealthScore(targetAngle, targetScore) {
  const ring = document.getElementById("health-score-ring");
  const numberEl = document.getElementById("health-score-number");
  if (!ring || !numberEl) return;
  ring.style.setProperty("--score", `${targetAngle}deg`);

  const duration = 900;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min(1, (now - start) / duration);
    numberEl.textContent = Math.round(targetScore * progress);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/* ---------------- AI Money Coach ---------------- */

let _chatHistory = [];

async function renderCoach() {
  const promptsRes = await Api.get("/assistant/prompts");
  const prompts = promptsRes.data;
  setTimeout(() => {
    const form = document.getElementById("coach-form");
    if (form) form.addEventListener("submit", async (e) => {
      e.preventDefault(); const input = document.getElementById("coach-input"); const text = input.value.trim(); if (!text) return; input.value = ""; await sendCoachMessage(text);
    });
    document.querySelectorAll("[data-coach-prompt]").forEach(btn => btn.addEventListener("click", () => sendCoachMessage(btn.dataset.coachPrompt)));
  }, 0);
  return `
    <div class="page-hero coach-hero"><div><span class="hero-kicker">YOUR PERSONAL MONEY GUIDE</span><h1>AI Money Coach</h1><p class="subtle" style="margin-top:6px;">Ask questions in normal language. The coach explains your real spending, saving and goals.</p></div><div class="hero-orb">${icon("chat",18)}</div></div>
    <div class="coach-prompts" style="margin:18px 0;">${prompts.map(p => `<button class="prompt-chip" type="button" data-coach-prompt="${escapeHtml(p)}">${escapeHtml(p)}</button>`).join("")}</div>
    <div class="card coach-card">
      <div class="coach-empty"><span>${icon("chart",18)}</span><strong>Try asking something like...</strong><p class="muted">"Where can I cut ₹2,000 this month?" or "Am I on track for my goal?"</p></div>
      <div id="chat-log" class="chat-log">${_chatHistory.map(m => `<div class="chat-bubble ${m.role}">${escapeHtml(m.text)}</div>`).join("")}</div>
      <form id="coach-form" class="coach-input-row"><input class="input" id="coach-input" placeholder="Ask about your money..." style="flex:1;"><button class="btn" type="submit">Send -></button></form>
    </div>
  `;
}

async function sendCoachMessage(text) {
  if (!text || !text.trim()) return;
  _chatHistory.push({ role: "user", text });
  const log = document.getElementById("chat-log");
  if (log) { log.innerHTML = _chatHistory.map(m => `<div class="chat-bubble ${m.role}">${escapeHtml(m.text)}</div>`).join(""); }
  try {
    const res = await Api.post("/assistant/ask", { question: text });
    _chatHistory.push({ role: "assistant", text: res.data.answer });
  } catch (err) {
    _chatHistory.push({ role: "assistant", text: "I couldn't answer that right now. Please try again." });
  }
  const html = await renderCoach();
  const content = document.getElementById("route-content"); if (content) content.innerHTML = html;
}

/* ---------------- Learn Money ---------------- */

async function renderLearn() {
  const res = await Api.get("/education/topics");
  const topics = res.data;
  return `
    <div class="page-hero learn-hero"><div><span class="hero-kicker">MONEY, WITHOUT THE JARGON</span><h1>Learn Money</h1><p class="subtle" style="margin-top:6px;">Short explanations, everyday examples and a simple "what should I do?" for each topic.</p></div><div class="hero-orb">${icon("book",18)}</div></div>
    <div class="learn-grid" style="margin-top:20px;">${topics.map((t, i) => card(`<div class="learn-number">${String(i+1).padStart(2,"0")}</div><h3 style="margin-top:8px;">${escapeHtml(t.title)}</h3><p style="margin-top:8px;line-height:1.6;">${escapeHtml(t.summary)}</p>${t.example ? `<div class="example-box"><strong>Example</strong><p class="muted" style="margin-top:4px;">${escapeHtml(t.example)}</p></div>` : ""}${t.action ? `<div class="learn-action"> ${escapeHtml(t.action)}</div>` : ""}`)).join("")}</div>
  `;
}

/* ---------------- Simulator ---------------- */

async function renderSimulator() {
  const compRes = await Api.get("/simulator/investment-comparison");
  setTimeout(() => {
    const form = document.getElementById("sim-form");
    if (form) form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const monthly = Number(document.getElementById("sim-monthly").value), years = Number(document.getElementById("sim-years").value), rate = Number(document.getElementById("sim-rate").value);
      try { const res = await Api.post("/simulator/compound-growth", { monthly_contribution_rupees: monthly, years, annual_return_pct: rate }); document.getElementById("sim-result").innerHTML = simResultHtml(res.data); } catch (err) { toast(err.message); }
    });
  }, 0);
  return `
    <div class="page-hero simulator-hero"><div><span class="hero-kicker">SEE THE POWER OF TIME</span><h1>Money Simulator</h1><p class="subtle" style="margin-top:6px;">Play with a monthly investment amount and see how regular investing may grow over time. This is an illustration, not a promise.</p></div><div class="hero-orb">${icon("chart",18)}</div></div>
    <div class="grid grid-2" style="margin-top:20px;align-items:start;">
      <div class="card simulator-card"><div class="eyebrow">Compound growth</div><h2 style="margin-top:5px;">What could my monthly investment become?</h2><p class="subtle" style="margin-top:6px;">Think of this like a "what if?" calculator. More time can matter as much as the amount you invest.</p>
        <form id="sim-form" style="margin-top:18px;">
          <div class="field"><label class="field-label">I invest every month (₹)</label><input class="input" type="number" min="1" id="sim-monthly" value="5000" required></div>
          <div class="field"><label class="field-label">I keep doing this for (years)</label><input class="input" type="number" min="1" max="60" id="sim-years" value="10" required></div>
          <div class="field"><label class="field-label">Example annual return (%)</label><input class="input" type="number" min="0" max="30" step="0.1" id="sim-rate" value="10" required><div class="muted" style="margin-top:5px;">Change this to see how assumptions affect the result. Real returns can be lower, higher or negative.</div></div>
          <button class="btn btn-block" type="submit">Show my illustration -></button>
        </form><div id="sim-result" style="margin-top:16px;"></div>
      </div>
      <div class="card"><div class="eyebrow">Common ways people invest or save</div><h2 style="margin-top:5px;">Which one is for what?</h2><div class="investment-cards" style="margin-top:14px;">${compRes.data.rows.map(r => `<div class="investment-row"><div><strong>${escapeHtml(r.option)}</strong><div class="muted" style="margin-top:3px;">Best for: ${escapeHtml(r.purpose || "planning")}</div></div><span class="badge badge-accent">${escapeHtml(r.risk)} risk</span><div class="muted">${escapeHtml(r.horizon)} horizon - ${escapeHtml(r.liquidity)} access</div></div>`).join("")}</div><div class="notice-box" style="margin-top:14px;">${icon("book",18)} <strong>Simple rule:</strong> keep emergency money easy to access; use longer-term investments only for money you can leave invested for longer.</div><p class="muted" style="margin-top:10px;">${escapeHtml(compRes.data.disclaimer)}</p></div>
    </div>
  `;
}

function simResultHtml(d) {
  return `<div class="sim-result"><div class="eyebrow">Illustration</div><div class="sim-result-number">${fmtMoney(d.future_value_rupees)}</div><p class="subtle">possible value after your selected period</p><div class="grid grid-2" style="margin-top:14px;gap:8px;"><div class="mini-stat"><span>You put in</span><strong>${fmtMoney(d.total_contribution_rupees)}</strong></div><div class="mini-stat"><span>Growth in this example</span><strong>+${fmtMoney(d.growth_rupees)}</strong></div></div><p class="muted" style="margin-top:12px;">${escapeHtml(d.disclaimer)}</p></div>`;
}

/* ---------------- Settings ---------------- */

function renderSettings() {
  return `
    <h1>Settings</h1>
    <div class="stack" style="margin-top:20px;max-width:480px;">
      <div class="card">
        <div class="eyebrow" style="margin-bottom:8px;">Profile</div>
        <p>${escapeHtml(State.user?.email || "")}</p>
      </div>
      <div class="card">
        <div class="eyebrow" style="margin-bottom:8px;">Financial Starting Score</div>
        <p class="subtle" style="margin-bottom:12px;">Take the beginner quiz to get a quick, transparent read on where you stand.</p>
        <button class="btn btn-ghost" onclick="navigate('quiz')">Take the Financial Quiz</button>
      </div>
      <div class="card">
        <div class="eyebrow" style="margin-bottom:8px;">Data & Privacy</div>
        <p class="subtle" style="margin-bottom:12px;">Permanently delete all your transactions from Finora. This cannot be undone.</p>
        <button class="btn btn-ghost" id="open-delete-data-btn" onclick="openDeleteDataModal()">Delete My Financial Data</button>
      </div>
      <div class="card">
        <div class="eyebrow" style="margin-bottom:8px;">Session</div>
        <button class="btn btn-ghost" onclick="logout()">Log out</button>
      </div>
    </div>
  `;
}

function openDeleteDataModal() {
  openModal("Delete My Financial Data", `
    <p class="subtle">This will permanently delete <strong>all</strong> of your transactions. Your goals, profile estimate, and account will stay - only transaction history is removed. This cannot be undone.</p>
    <div id="delete-data-error"></div>
    <div class="row" style="gap:10px;margin-top:18px;">
      <button class="btn btn-ghost" style="flex:1;" id="delete-data-cancel-btn" onclick="closeModal()">Cancel</button>
      <button class="btn" style="flex:1;background:var(--red, #dc2626);" id="delete-data-confirm-btn" onclick="confirmDeleteAllData()">Yes, delete everything</button>
    </div>
  `);
}

async function confirmDeleteAllData() {
  const btn = document.getElementById("delete-data-confirm-btn");
  const cancelBtn = document.getElementById("delete-data-cancel-btn");
  const errorEl = document.getElementById("delete-data-error");
  btn.disabled = true;
  cancelBtn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "Deleting...";
  errorEl.innerHTML = "";

  try {
    const res = await Api.del("/transactions/data/all");
    closeModal();
    toast(`Deleted ${res.data.deleted} transaction(s). Your data is gone.`);
    render(); // re-render current view so any cached counts/lists reflect the deletion
  } catch (err) {
    errorEl.innerHTML = `<p class="subtle" style="color:var(--red, #dc2626);margin-top:10px;">Couldn't delete your data: ${escapeHtml(err.message)}. Please try again.</p>`;
    btn.disabled = false;
    cancelBtn.disabled = false;
    btn.textContent = originalText;
  }
}

/* ---------------- Admin ---------------- */
/* Surfaces GET /admin/overview and GET /admin/audit-logs (with its page,
   page_size, action, user_id filters), which previously had no UI - only
   reachable via /docs or a raw API call. Route + nav item are admin-gated
   in app.js / components.js; the backend enforces the same via require_admin. */

let _adminAuditFilters = { page: 1, page_size: 20, action: "", user_id: "" };

async function renderAdmin() {
  const [overviewRes, logsRes] = await Promise.all([
    Api.get("/admin/overview"),
    Api.get(`/admin/audit-logs?${adminAuditQueryString()}`),
  ]);
  const o = overviewRes.data;
  const logs = logsRes.data;
  const meta = logsRes.meta || {};
  const totalPages = Math.max(1, Math.ceil((meta.total || 0) / (meta.page_size || _adminAuditFilters.page_size)));

  setTimeout(() => attachAdminAuditHandlers(), 0);

  return `
    <div class="page-hero admin-hero">
      <div><span class="hero-kicker">SYSTEM OVERVIEW</span><h1>Admin</h1><p class="subtle" style="margin-top:6px;">Account activity and audit history across Finora.</p></div>
      <div class="hero-orb">${icon("settings", 30)}</div>
    </div>
    <div class="grid grid-3" style="margin-top:20px;">
      ${card(`<div class="eyebrow">Total users</div><div class="big-number" style="margin-top:6px;">${o.total_users}</div>`)}
      ${card(`<div class="eyebrow">Total transactions</div><div class="big-number" style="margin-top:6px;">${o.total_transactions}</div>`)}
      ${card(`<div class="eyebrow">Beginner-mode users</div><div class="big-number" style="margin-top:6px;">${o.beginner_mode_users}</div>`)}
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="row-between" style="flex-wrap:wrap;gap:12px;">
        <div class="eyebrow">Audit log</div>
        <div class="row" style="gap:8px;flex-wrap:wrap;">
          <input class="input" id="admin-filter-action" placeholder="Filter by action (e.g. login)" style="width:auto;min-width:200px;" value="${escapeHtml(_adminAuditFilters.action)}">
          <input class="input" id="admin-filter-user-id" type="number" min="1" placeholder="User ID" style="width:auto;min-width:110px;" value="${escapeHtml(String(_adminAuditFilters.user_id))}">
          <button class="btn btn-secondary btn-sm" id="admin-filter-apply">Apply</button>
          <button class="btn btn-ghost btn-sm" id="admin-filter-clear">Clear</button>
        </div>
      </div>
      <div style="margin-top:16px;">
        ${logs.length ? adminAuditTableHtml(logs) : emptyState(icon("clipboard", 24), "No audit log entries", "Nothing matches these filters yet.")}
      </div>
      ${logs.length ? `
      <div class="row-between" style="margin-top:14px;">
        <span class="muted">Page ${meta.page} of ${totalPages} · ${meta.total} total</span>
        <div class="row" style="gap:8px;">
          <button class="btn btn-ghost btn-sm" id="admin-page-prev" ${meta.page <= 1 ? "disabled" : ""}>Previous</button>
          <button class="btn btn-ghost btn-sm" id="admin-page-next" ${meta.page >= totalPages ? "disabled" : ""}>Next</button>
        </div>
      </div>` : ""}
    </div>
  `;
}

function adminAuditQueryString() {
  const params = new URLSearchParams({ page: _adminAuditFilters.page, page_size: _adminAuditFilters.page_size });
  if (_adminAuditFilters.action) params.set("action", _adminAuditFilters.action);
  if (_adminAuditFilters.user_id) params.set("user_id", _adminAuditFilters.user_id);
  return params.toString();
}

function adminAuditTableHtml(logs) {
  return `<div style="overflow-x:auto;"><table class="txn-table">
    <thead><tr><th>Time</th><th>User ID</th><th>Action</th><th>Detail</th></tr></thead>
    <tbody>
      ${logs.map(l => `<tr>
        <td class="muted">${escapeHtml(new Date(l.created_at).toLocaleString("en-IN"))}</td>
        <td>${l.user_id ?? "-"}</td>
        <td><span class="badge badge-accent">${escapeHtml(l.action)}</span></td>
        <td class="subtle">${escapeHtml(l.detail || "-")}</td>
      </tr>`).join("")}
    </tbody>
  </table></div>`;
}

async function refreshAdminAuditView() {
  const html = await renderAdmin();
  const contentEl = document.getElementById("route-content");
  if (contentEl) contentEl.innerHTML = html;
}

function attachAdminAuditHandlers() {
  const applyBtn = document.getElementById("admin-filter-apply");
  const clearBtn = document.getElementById("admin-filter-clear");
  const prevBtn = document.getElementById("admin-page-prev");
  const nextBtn = document.getElementById("admin-page-next");

  if (applyBtn) applyBtn.addEventListener("click", () => {
    _adminAuditFilters.action = document.getElementById("admin-filter-action").value.trim();
    _adminAuditFilters.user_id = document.getElementById("admin-filter-user-id").value.trim();
    _adminAuditFilters.page = 1;
    refreshAdminAuditView();
  });
  if (clearBtn) clearBtn.addEventListener("click", () => {
    _adminAuditFilters = { page: 1, page_size: 20, action: "", user_id: "" };
    refreshAdminAuditView();
  });
  if (prevBtn) prevBtn.addEventListener("click", () => {
    _adminAuditFilters.page = Math.max(1, _adminAuditFilters.page - 1);
    refreshAdminAuditView();
  });
  if (nextBtn) nextBtn.addEventListener("click", () => {
    _adminAuditFilters.page = _adminAuditFilters.page + 1;
    refreshAdminAuditView();
  });
}

function logout() { Api.clearToken(); State.user = null; navigate("landing"); render(); }

function renderRegister() {
  setTimeout(() => {
    document.getElementById("register-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("reg-name").value.trim();
      const email = document.getElementById("reg-email").value.trim();
      const password = document.getElementById("reg-password").value;
      const btn = document.getElementById("register-btn");
      if (password.length < 8) { toast("Password must be at least 8 characters."); return; }
      btn.disabled = true; btn.textContent = "Creating account...";
      try {
        const res = await Api.post("/auth/register", { name, email, password });
        Api.setToken(res.data.access_token);
        State.user = { id: res.data.user_id, name: res.data.name, email: res.data.email, is_beginner: res.data.is_beginner };
        navigate("onboarding");
        render();
      } catch (err) {
        toast(err.message);
        btn.disabled = false; btn.textContent = "Create account";
      }
    });
  }, 0);

  return `
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;">
    <div class="card" style="max-width:380px;width:100%;">
      <h2 style="margin-bottom:4px;">${getTimeGreeting()}</h2>
      <p class="subtle" style="margin-bottom:20px;">Let's understand your money.</p>
      <form id="register-form">
        <div class="field">
          <label class="field-label">Name</label>
          <input class="input" type="text" id="reg-name" required>
        </div>
        <div class="field">
          <label class="field-label">Email</label>
          <input class="input" type="email" id="reg-email" required>
        </div>
        <div class="field">
          <label class="field-label">Password</label>
          <input class="input" type="password" id="reg-password" minlength="8" required>
          <div class="muted" style="margin-top:4px;">At least 8 characters.</div>
        </div>
        <button class="btn btn-block" id="register-btn" type="submit">Start Free</button>
      </form>
      <p class="subtle" style="margin-top:16px;text-align:center;">
        Already have an account? <a href="#/login" style="color:var(--accent);font-weight:600;">Log in</a>
      </p>
    </div>
  </div>`;
}
