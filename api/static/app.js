const app = document.querySelector("#app");
const HISTORY_STORAGE_KEY = "hybrid-rag-chat-history-v1";
const state = {
  user: null,
  conversations: [],
  activeConversationId: null,
  suggestions: [],
  suggestionsLoading: false,
  suggestionRequestId: 0,
  historySaveWarned: false,
};
const passwordPolicy = /^(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[!@#$%^&*]).{9,1024}$/;
const passwordPolicyHint = "Use at least nine characters, including at least one uppercase letter, one lowercase letter, one numeral, and one permitted symbol (! @ # $ % ^ & *).";

const icons = {
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowDown: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v6h6M10 14h6M10 17h6"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"/><path d="M9.9 5.2A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a15 15 0 0 1-3.1 3.8M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7c1.6 0 3-.4 4.2-1"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  logout: '<path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 9a7 7 0 0 1 11.6-2L20 12M4 12l2.8 5a7 7 0 0 0 11.6-2"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/>',
  shield: '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
  sparkle: '<path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM19 15l1 2.5 2.5 1-2.5 1L19 22l-1-2.5-2.5-1 2.5-1L19 15Z"/>',
  trend: '<path d="m3 17 6-6 4 4 8-9"/><path d="M15 6h6v6"/>',
};

function icon(name, cls = "") {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.doc}</svg>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function activeConversation() {
  return state.conversations.find((conversation) => conversation.id === state.activeConversationId);
}

function isStoredConversation(value) {
  return value && typeof value.id === "string" && typeof value.title === "string" &&
    Number.isInteger(value.selected) && Array.isArray(value.turns) &&
    value.turns.every((turn) => turn && typeof turn.question === "string" &&
      typeof turn.answer === "string" && Array.isArray(turn.citations));
}

function restoreChatHistory() {
  try {
    const stored = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!stored) return;
    const history = JSON.parse(stored);
    if (history.email !== state.user.email || !Array.isArray(history.conversations)) return;
    state.conversations = history.conversations.filter(isStoredConversation);
    let interrupted = false;
    state.conversations = state.conversations.map((conversation) => ({
      ...conversation,
      turns: conversation.turns.map((turn) => {
        if (turn.status !== "pending") return turn;
        interrupted = true;
        return {
          ...turn,
          answer: "This question was interrupted before the answer finished. Please ask it again.",
          status: "error",
        };
      }),
    }));
    state.activeConversationId = state.conversations.some(
      (conversation) => conversation.id === history.activeConversationId,
    ) ? history.activeConversationId : null;
    if (interrupted) saveChatHistory();
  } catch (error) {
    state.conversations = [];
    state.activeConversationId = null;
    showToast(`Previous chat history could not be restored: ${error.message}`);
  }
}

function saveChatHistory() {
  if (!state.user) return;
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify({
      email: state.user.email,
      activeConversationId: state.activeConversationId,
      conversations: state.conversations,
    }));
  } catch (error) {
    if (!state.historySaveWarned) {
      state.historySaveWarned = true;
      showToast(`Chat history could not be saved in this browser: ${error.message}`);
    }
  }
}

function clearStoredChatHistory() {
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
  } catch (error) {
    showToast(`Signed out, but saved chat history could not be cleared from this tab: ${error.message}`);
  }
}

async function fetchSuggestions(exclude = []) {
  const params = new URLSearchParams();
  exclude.forEach((key) => params.append("exclude", key));
  const query = params.toString();
  const data = await requestJson(`/suggestions${query ? `?${query}` : ""}`);
  if (!Array.isArray(data.suggestions)) {
    throw new Error("The document suggestions response was invalid.");
  }
  return data.suggestions.filter((suggestion) =>
    suggestion && typeof suggestion.key === "string" &&
    typeof suggestion.question === "string" && typeof suggestion.source === "string");
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new Error(data.detail || `The request failed (${response.status}).`);
  }
  return data;
}

function showAuth(mode = "login", message = "") {
  const registering = mode === "register";
  app.innerHTML = `
    <main class="auth-screen">
      <section class="auth-brand" aria-label="About Index">
        <div class="brand-row"><span class="brand-mark">i</span><span class="brand-name">Index</span></div>
        <div class="brand-copy">
          <div class="eyebrow">A quieter way to find the point</div>
          <h1>Your documents, in conversation.</h1>
          <p>Bring the important details together. Ask a clear question and follow every answer back to its source.</p>
        </div>
        <div class="brand-note">${icon("shield")} Private by design · Answers grounded in your sources</div>
      </section>
      <section class="auth-main">
        <div class="auth-card">
          <div class="eyebrow">${registering ? "Create your account" : "Welcome back"}</div>
          <h2>${registering ? "Start with your sources." : "Good to have you back."}</h2>
          <p class="auth-intro">${registering ? "Create a user account to start asking questions." : "Sign in to continue to your document library."}</p>
          <form class="auth-form" id="auth-form">
            <div class="field">
              <label for="auth-email">Email address</label>
              <input id="auth-email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required maxlength="254">
            </div>
            <div class="field">
              <label for="auth-password">Password</label>
              <div class="password-control">
                <input id="auth-password" name="password" type="password" autocomplete="${registering ? "new-password" : "current-password"}" placeholder="${registering ? "Create a strong password" : "Your password"}" required minlength="${registering ? "9" : "1"}" maxlength="1024">
                <button class="password-toggle" type="button" data-password-toggle="auth-password" aria-label="Show password" aria-pressed="false" title="Show password">${icon("eye")}</button>
              </div>
            </div>
            ${registering ? `<div class="field">
              <label for="auth-confirm-password">Confirm password</label>
              <div class="password-control">
                <input id="auth-confirm-password" name="confirmPassword" type="password" autocomplete="new-password" placeholder="Enter your password again" required minlength="9" maxlength="1024">
                <button class="password-toggle" type="button" data-password-toggle="auth-confirm-password" aria-label="Show confirm password" aria-pressed="false" title="Show confirm password">${icon("eye")}</button>
              </div>` : ""}
              ${registering ? `<span class="field-hint">${passwordPolicyHint}</span></div>` : ""}
            <p class="auth-error" id="auth-error" role="alert">${escapeHtml(message)}</p>
            <button class="primary-button" type="submit">${registering ? "Create account" : "Sign in"} ${icon("arrow")}</button>
          </form>
          <p class="auth-switch">${registering
            ? 'Already have an account? <button class="text-button" id="switch-auth" type="button">Sign in</button>'
            : 'New to Index? <button class="text-button" id="switch-auth" type="button">Create an account</button>'}</p>
          <div class="auth-footnote">All new accounts have standard document access. Administrator access is provisioned separately.</div>
        </div>
      </section>
    </main>`;

  document.querySelector("#switch-auth").addEventListener("click", () => showAuth(registering ? "login" : "register"));
  document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const input = document.getElementById(toggle.dataset.passwordToggle);
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      toggle.setAttribute("aria-pressed", String(visible));
      toggle.setAttribute("aria-label", `${visible ? "Hide" : "Show"} ${input.name === "confirmPassword" ? "confirm password" : "password"}`);
      toggle.title = `${visible ? "Hide" : "Show"} password`;
      toggle.innerHTML = icon(visible ? "eyeOff" : "eye");
    });
  });
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    const error = document.querySelector("#auth-error");
    const email = form.elements.email.value.trim();
    const password = form.elements.password.value;
    if (registering && !passwordPolicy.test(password)) {
      error.textContent = passwordPolicyHint;
      return;
    }
    if (registering && password !== form.elements.confirmPassword.value) {
      error.textContent = "The passwords do not match.";
      return;
    }
    button.disabled = true;
    error.textContent = "";
    try {
      state.user = await requestJson(registering ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    } catch (err) {
      error.textContent = err.message;
      button.disabled = false;
      return;
    }
    state.conversations = [];
    state.activeConversationId = null;
    state.suggestions = [];
    state.historySaveWarned = false;
    restoreChatHistory();
    try {
      state.suggestions = await fetchSuggestions();
    } catch (err) {
      showToast(`Document-based suggestions could not be loaded: ${err.message}`);
    }
    showWorkspace();
  });
}

function header() {
  const admin = state.user.role === "admin";
  return `<header class="app-header">
    <div class="top-brand"><span class="brand-mark">i</span><span class="brand-name">Index</span><span class="header-caption">Document intelligence</span></div>
    <div class="header-actions">
      <span class="role-pill ${admin ? "admin" : ""}"><i class="role-dot"></i>${admin ? "Administrator" : "User"} · ${admin ? "All documents" : "Public library"}</span>
      <span class="user-email">${escapeHtml(state.user.email)}</span>
      <button class="icon-button logout-button" id="logout" type="button" aria-label="Sign out" title="Sign out">${icon("logout")} Sign out</button>
    </div>
  </header>`;
}

function showWorkspace() {
  app.innerHTML = `<div class="app-frame">${header()}<main id="workspace-root"></main></div>`;
  document.querySelector("#logout").addEventListener("click", signOut);
  if (activeConversation()?.turns.length) renderConversation();
  else renderWelcome();
}

function composerMarkup(id, placeholder, welcome = false) {
  return `<form class="composer ${welcome ? "welcome-composer" : ""}" id="${id}">
    <textarea name="question" aria-label="Ask your documents" placeholder="${placeholder}" rows="${welcome ? 2 : 1}" required></textarea>
    <div class="composer-footer">
      <span class="composer-hint">Enter to ask · Shift + Enter for a new line</span>
      <button class="ask-button" type="submit">Ask ${icon("arrow")}</button>
    </div>
  </form>`;
}

function bindComposer(id) {
  const form = document.querySelector(`#${id}`);
  const textarea = form.querySelector("textarea");
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitQuestion(textarea.value);
  });
}

function renderWelcome() {
  document.querySelector(".app-frame")?.classList.remove("conversation-active");
  const root = document.querySelector("#workspace-root");
  const hasHistory = state.conversations.some((conversation) => conversation.turns.length);
  const admin = state.user.role === "admin";
  const welcome = `<section class="welcome-main">
    <div class="welcome-heading">
      <div class="eyebrow">A good place to begin</div>
      <h1>What would you like to understand?</h1>
      <p>Ask a question about your documents. Answers draw on your sources, with citations so you can check the details.</p>
    </div>
    ${composerMarkup("welcome-form", "Ask a question about your documents…", true)}
    <div class="suggestion-heading"><span>Questions from your documents</span><button class="icon-button suggestion-refresh" id="refresh-suggestions" type="button">${icon("refresh")} Shuffle</button></div>
    <div class="suggestion-list"></div>
    <div class="welcome-foot">Suggested questions are based on documents available to your account.</div>
  </section>`;
  root.innerHTML = hasHistory
    ? `<div class="workspace ${admin ? "is-admin" : ""}">${renderSidebar()}<section class="conversation-main welcome-chat-main">${welcome}</section>${renderMetrics(null)}</div>`
    : welcome;
  renderSuggestionList();
  bindComposer("welcome-form");
  bindHistoryPanel();
  document.querySelector("#refresh-suggestions").addEventListener("click", refreshSuggestions);
}

function renderSuggestionList() {
  const list = document.querySelector(".suggestion-list");
  if (!list) return;
  if (state.suggestionsLoading) {
    list.innerHTML = '<div class="suggestion-empty">Finding questions from your documents…</div>';
  } else if (state.suggestions.length) {
    list.innerHTML = state.suggestions.map((suggestion) => `
      <button class="suggestion" type="button" data-suggestion="${escapeHtml(suggestion.question)}">
        ${icon("sparkle")}
        <span class="suggestion-copy"><span>${escapeHtml(suggestion.question)}</span><small>${escapeHtml(suggestion.source)}</small></span>
      </button>`).join("");
    list.querySelectorAll(".suggestion").forEach((button) => {
      button.addEventListener("click", () => submitQuestion(button.dataset.suggestion));
    });
  } else {
    list.innerHTML = '<div class="suggestion-empty">No document topics are available yet. You can still ask a question above.</div>';
  }
}

async function refreshSuggestions() {
  const requestId = ++state.suggestionRequestId;
  const exclude = state.suggestions.map((suggestion) => suggestion.key);
  state.suggestionsLoading = true;
  renderSuggestionList();
  const button = document.querySelector("#refresh-suggestions");
  if (!button) {
    state.suggestionsLoading = false;
    return;
  }
  button.disabled = true;
  button.innerHTML = `${icon("refresh")} Shuffling…`;
  try {
    const suggestions = await fetchSuggestions(exclude);
    if (requestId === state.suggestionRequestId) state.suggestions = suggestions;
  } catch (error) {
    if (requestId === state.suggestionRequestId) {
      showToast(`Document-based suggestions could not be refreshed: ${error.message}`);
    }
  } finally {
    if (requestId === state.suggestionRequestId) {
      state.suggestionsLoading = false;
      const currentButton = document.querySelector("#refresh-suggestions");
      if (currentButton) {
        currentButton.disabled = false;
        currentButton.innerHTML = `${icon("refresh")} Shuffle`;
      }
      renderSuggestionList();
    }
  }
}

function questionLabel(question) {
  const text = question.replace(/\s+/g, " ").trim();
  return text.length > 78 ? `${text.slice(0, 75)}…` : text;
}

function renderSidebar() {
  const conversations = state.conversations.filter((conversation) => conversation.turns.length);
  return `<aside class="history-panel">
    <div class="history-top"><button class="new-chat-button" id="new-chat" type="button" aria-current="${state.activeConversationId === null}">${icon("plus")} New question</button></div>
    <div class="history-label">Recent chats</div>
    <nav class="history-list" aria-label="Recent chats">
      ${conversations.length ? conversations.map((conversation) => `<button class="history-item" data-chat-id="${escapeHtml(conversation.id)}" aria-current="${conversation.id === state.activeConversationId}">${icon("clock")}<span>${escapeHtml(questionLabel(conversation.title))}</span></button>`).join("") : '<div class="history-empty">Your chats will appear here.</div>'}
    </nav>
    <div class="history-foot">Your chat history stays available until you sign out.</div>
  </aside>`;
}

function bindHistoryPanel() {
  document.querySelector("#new-chat")?.addEventListener("click", () => {
    state.activeConversationId = null;
    state.suggestionRequestId++;
    saveChatHistory();
    renderWelcome();
    refreshSuggestions();
  });
  document.querySelectorAll("[data-chat-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeConversationId = button.dataset.chatId;
      state.suggestionRequestId++;
      state.suggestionsLoading = false;
      saveChatHistory();
      showWorkspace();
    });
  });
}
function renderInlineMarkdown(text, turnIndex) {
  const placeholders = [];
  const hold = (html) => {
    const token = `\u0001${placeholders.length}\u0002`;
    placeholders.push(html);
    return token;
  };
  let html = escapeHtml(text);
  html = html.replace(/`([^`\n]+)`/g, (_, code) => hold(`<code>${code}</code>`));
  html = html.replace(/\[(\d+)\]/g, (_, number) => hold(
    `<button class="citation-chip" type="button" data-citation-turn="${turnIndex}" data-citation="${number}" aria-label="Show source ${number}">[${number}]</button>`,
  ));
  html = html.replace(/\*\*(.+?)\*\*|__(.+?)__/g, (_, a, b) => `<strong>${a || b}</strong>`);
  html = html.replace(/~~(.+?)~~/g, "<del>$1</del>");
  html = html.replace(/(^|[^\w*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[^\w_])_([^_\n]+)_(?![\w_])/g, "$1<em>$2</em>");
  return placeholders.reduce((result, value, index) => result.replace(`\u0001${index}\u0002`, value), html);
}

function renderAnswerText(answer, turnIndex) {
  const source = answer.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/\r\n?/g, "\n");
  const lines = source.split("\n");
  const blocks = [];
  const isFence = (line) => /^\s*(```|~~~)/.test(line);
  const isUnordered = (line) => /^\s*[-*+]\s+/.test(line);
  const isOrdered = (line) => /^\s*\d+[.)]\s+/.test(line);
  const isBlockStart = (line) => isFence(line) || /^#{1,6}\s+/.test(line) ||
    isUnordered(line) || isOrdered(line) || /^\s*>/.test(line) || /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line);

  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    if (!line.trim()) {
      index++;
      continue;
    }
    if (isFence(line)) {
      const marker = line.trim().slice(0, 3);
      const code = [];
      index++;
      while (index < lines.length && !lines[index].trimStart().startsWith(marker)) {
        code.push(lines[index++]);
      }
      if (index < lines.length) index++;
      blocks.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const level = heading[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2], turnIndex)}</h${level}>`);
      index++;
      continue;
    }
    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push("<hr>");
      index++;
      continue;
    }
    if (isUnordered(line) || isOrdered(line)) {
      const ordered = isOrdered(line);
      const listItems = [];
      while (index < lines.length && (ordered ? isOrdered(lines[index]) : isUnordered(lines[index]))) {
        const item = lines[index++].replace(ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*+]\s+/, "");
        listItems.push(`<li>${renderInlineMarkdown(item, turnIndex)}</li>`);
      }
      const tag = ordered ? "ol" : "ul";
      blocks.push(`<${tag}>${listItems.join("")}</${tag}>`);
      continue;
    }
    if (/^\s*>/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) {
        quote.push(lines[index++].replace(/^\s*>\s?/, ""));
      }
      blocks.push(`<blockquote>${renderInlineMarkdown(quote.join(" "), turnIndex)}</blockquote>`);
      continue;
    }
    const paragraph = [line.trim()];
    index++;
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
      paragraph.push(lines[index++].trim());
    }
    blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "), turnIndex)}</p>`);
  }
  return blocks.join("");
}

function renderSources(turn, turnIndex) {
  if (!turn.citations || !turn.citations.length) return "";
  return `<div class="source-list" aria-label="Sources">${turn.citations.map((source) => `
    <details class="source-card" id="source-${turnIndex}-${source.n}">
      <summary><span class="source-number">${source.n}</span><span class="source-title">${escapeHtml(source.title)} · ${escapeHtml(source.section)}</span><span class="source-version">${escapeHtml(source.version)}${source.is_latest ? "" : " · older"}</span></summary>
      <p>${escapeHtml(source.text)}</p>
    </details>`).join("")}</div>`;
}

function renderTurn(turn, index) {
  const pending = turn.status === "pending";
  const notice = turn.status === "abstained" ? "The available documents did not provide enough information to answer." :
    turn.status === "blocked" ? "This request was stopped by the safety check." : "";
  return `<article class="message" id="turn-${index}">
    <div class="question-bubble">${escapeHtml(turn.question)}</div>
    <div class="answer-block">
      <div class="answer-label"><span class="brand-mark">i</span> Index</div>
      <div class="answer-text ${pending || turn.status === "abstained" ? "muted" : ""}">${pending ? "Searching your documents…" : renderAnswerText(turn.answer || "The request failed. Please try again.", index)}</div>
      ${notice ? `<div class="message-notice">${notice}</div>` : ""}
      ${!pending ? renderSources(turn, index) : ""}
    </div>
  </article>`;
}

function renderMetrics(turn) {
  if (state.user.role !== "admin") return "";
  if (!turn || !turn.trace) {
    return `<aside class="metrics-panel"><h2 class="metrics-heading">${icon("trend")} Request metrics</h2><p class="metrics-caption">Stage timings for the selected answer.</p><div class="metrics-empty">Metrics will appear here after you ask a question.</div></aside>`;
  }
  const trace = turn.trace;
  const timings = trace.timings_ms || {};
  const stageNames = ["guard", "embed", "cache", "router", "retrieve", "generate"];
  const stages = stageNames.filter((name) => timings[name] !== undefined);
  const max = Math.max(1, ...stages.map((name) => Number(timings[name]) || 0));
  const cacheLabel = trace.cache_hit ? `${trace.cache_tier || "response"} hit` : "miss";
  return `<aside class="metrics-panel">
    <h2 class="metrics-heading">${icon("trend")} Request metrics</h2>
    <p class="metrics-caption">Stage timings for the selected answer.</p>
    <div class="metric-total"><span>Total time</span><strong>${escapeHtml(timings.total ?? "—")}<small style="font:400 11px var(--sans)"> ms</small></strong></div>
    <div class="metric-meta">
      <div><span>Retrieval depth</span><strong>k = ${escapeHtml(trace.k ?? "—")}</strong></div>
      <div><span>Cache</span><strong>${escapeHtml(cacheLabel)}</strong></div>
      <div><span>Guard</span><strong>${escapeHtml(trace.guard ?? "—")}</strong></div>
      <div><span>Tokens</span><strong>${escapeHtml(trace.tokens ?? "—")}</strong></div>
    </div>
    <div class="metrics-label">Latency by stage</div>
    ${stages.map((name) => `<div class="metric-row"><span>${escapeHtml(name)}</span><div class="metric-track"><i style="width:${Math.max(1, (Number(timings[name]) / max) * 100)}%"></i></div><span class="value">${escapeHtml(timings[name])} ms</span></div>`).join("")}
    <div class="metrics-note">Timings describe this request only. Model-provider latency can vary between requests.</div>
  </aside>`;
}

function renderConversation() {
  document.querySelector(".app-frame")?.classList.add("conversation-active");
  const root = document.querySelector("#workspace-root");
  const conversation = activeConversation();
  if (!conversation?.turns.length) {
    renderWelcome();
    return;
  }
  const admin = state.user.role === "admin";
  const current = conversation.turns[conversation.selected] || conversation.turns[conversation.turns.length - 1];
  root.innerHTML = `<div class="workspace ${admin ? "is-admin" : ""}">
    ${renderSidebar()}
    <section class="conversation-main">
      <header class="conversation-title"><div><h1>${escapeHtml(conversation.title)}</h1><div class="sub">Answers grounded in your available documents</div></div></header>
      <div class="conversation-stream" id="conversation-stream"><div class="message-stack">${conversation.turns.map(renderTurn).join("")}</div></div>
      <div class="reply-form">
        <button class="jump-to-latest" id="jump-to-latest" type="button" aria-label="Jump to the latest message" title="Jump to the latest message" hidden>${icon("arrowDown")}<span>Latest</span></button>
        ${composerMarkup("reply-form", "Ask a follow-up…")}
      </div>
      <div class="conversation-footer">Review cited passages to verify important details.</div>
    </section>
    ${renderMetrics(current)}
  </div>`;
  bindHistoryPanel();
  document.querySelectorAll(".citation-chip").forEach((button) => {
    button.addEventListener("click", () => {
      const source = document.querySelector(`#source-${button.dataset.citationTurn}-${button.dataset.citation}`);
      if (source) {
        source.open = true;
        source.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });
  bindComposer("reply-form");
  const stream = document.querySelector("#conversation-stream");
  const jumpButton = document.querySelector("#jump-to-latest");
  const updateJumpButton = () => {
    jumpButton.hidden = stream.scrollHeight - stream.scrollTop - stream.clientHeight <= 120;
  };
  stream.addEventListener("scroll", updateJumpButton, { passive: true });
  jumpButton.addEventListener("click", () => {
    stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
  });
  stream.style.scrollBehavior = "auto";
  stream.scrollTop = stream.scrollHeight;
  stream.style.removeProperty("scroll-behavior");
  updateJumpButton();
}

async function submitQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed) return;
  let conversation = activeConversation();
  if (!conversation) {
    conversation = {
      id: crypto.randomUUID(),
      title: questionLabel(trimmed),
      selected: -1,
      turns: [],
    };
    state.conversations.unshift(conversation);
    state.activeConversationId = conversation.id;
  }
  const index = conversation.turns.length;
  conversation.turns.push({
    question: trimmed,
    answer: "",
    status: "pending",
    citations: [],
    trace: null,
  });
  conversation.selected = index;
  saveChatHistory();
  showWorkspace();
  const currentButton = document.querySelector(".ask-button");
  if (currentButton) currentButton.disabled = true;
  try {
    const response = await requestJson("/ask", {
      method: "POST",
      body: JSON.stringify({ question: trimmed }),
    });
    conversation.turns[index] = { question: trimmed, ...response };
  } catch (error) {
    conversation.turns[index] = {
      question: trimmed,
      answer: error.message,
      status: "error",
      citations: [],
      trace: null,
    };
  }
  saveChatHistory();
  if (state.activeConversationId === conversation.id) showWorkspace();
  if (conversation.turns[index].status === "error") showToast(conversation.turns[index].answer);
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "alert");
  toast.textContent = message;
  document.body.append(toast);
  window.setTimeout(() => toast.remove(), 6000);
}

async function signOut() {
  const button = document.querySelector("#logout");
  button.disabled = true;
  try {
    await requestJson("/auth/logout", { method: "POST", body: "{}" });
    state.suggestionRequestId++;
    state.suggestionsLoading = false;
    clearStoredChatHistory();
    state.user = null;
    state.conversations = [];
    state.activeConversationId = null;
    state.suggestions = [];
    showAuth("login");
  } catch (error) {
    button.disabled = false;
    showToast(error.message);
  }
}

async function start() {
  try {
    state.user = await requestJson("/auth/me");
  } catch (error) {
    if (error.message !== "Please sign in.") showToast(error.message);
    showAuth("login");
    return;
  }
  restoreChatHistory();
  try {
    state.suggestions = await fetchSuggestions();
  } catch (error) {
    showToast(`Document-based suggestions could not be loaded: ${error.message}`);
  }
  showWorkspace();
}

start();
