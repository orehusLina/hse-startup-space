"use strict";

// ---------- labels ----------
const KIND = { startup: "Стартап", vacancy: "Вакансия" };
const STAGE = { idea: "Идея", mvp: "MVP", early_revenue: "Первая выручка", growth: "Рост" };
const FORMAT = { remote: "Удалённо", office: "Офис", hybrid: "Гибрид" };
const POST_STATUS = { active: "Активна", paused: "На паузе", closed: "Закрыта" };
const RESP_STATUS = { pending: "На рассмотрении", accepted: "Принят", rejected: "Отклонён", withdrawn: "Отозван" };

// ---------- utils ----------
const $app = document.getElementById("app");
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const initials = (name) => name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
};
const spinner = () => `<div class="spinner" aria-label="Загрузка"></div>`;
const empty = (icon, text, action = "") => `<div class="empty"><div class="big">${icon}</div><p>${text}</p>${action}</div>`;
const badge = (cls, text) => `<span class="badge b-${esc(cls)}">${esc(text)}</span>`;
const chips = (skills, active) =>
  skills?.length
    ? `<div class="chips">${skills
        .map((s) => `<span class="chip ${active && s.toLowerCase() === active.toLowerCase() ? "on" : ""}" data-skill="${esc(s)}">${esc(s)}</span>`)
        .join("")}</div>`
    : "";

let toastTimer;
function toast(text, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.className = `toast show ${isError ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 2600);
}

// ---------- Telegram ----------
const tg = window.Telegram?.WebApp;
if (tg?.initData) {
  document.documentElement.classList.add("tg");
  tg.ready();
  tg.expand();
  tg.BackButton.onClick(() => history.back());
}
const haptic = (type) => tg?.HapticFeedback?.notificationOccurred?.(type);

// ---------- API ----------
const auth = {
  get token() { return localStorage.getItem("token"); },
  set(token, user) { localStorage.setItem("token", token); auth.user = user; },
  clear() { localStorage.removeItem("token"); auth.user = null; },
  user: null,
};

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(path, location.origin);
  Object.entries(params || {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && url.searchParams.set(k, v));
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Нет соединения с сервером");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && path !== "/api/auth/login") {
      auth.clear();
      location.hash = "#/login";
    }
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join("; ");
    throw new ApiError(res.status, msg || `Ошибка ${res.status}`);
  }
  return data;
}

// ---------- router ----------
const routes = [
  [/^#\/login$/, viewLogin, { public: true }],
  [/^#\/feed$/, viewFeed, { tab: "feed" }],
  [/^#\/post\/(\d+)$/, viewPost, { tab: "feed", back: true }],
  [/^#\/new$/, (_) => viewForm(null), { tab: "new" }],
  [/^#\/edit\/(\d+)$/, (m) => viewForm(+m[1]), { tab: "me", back: true }],
  [/^#\/me\/(profile|posts|sent|received)$/, viewCabinet, { tab: "me" }],
];

async function router() {
  const hash = location.hash || "#/feed";
  const match = routes.find(([re]) => re.test(hash));
  if (!match) return (location.hash = "#/feed");
  const [re, view, opts] = match;

  if (!opts.public && !auth.token) return (location.hash = "#/login");
  if (!opts.public && !auth.user) {
    try { auth.user = await api("/api/me"); } catch { return; }
  }
  document.getElementById("topbar").hidden = !!opts.public;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.tab === opts.tab));
  if (tg) opts.back ? tg.BackButton.show() : tg.BackButton.hide();
  if (!opts.public) refreshBadge();

  $app.innerHTML = spinner();
  window.scrollTo(0, 0);
  try {
    await view(hash.match(re));
  } catch (e) {
    if (e.status === 401) return;
    $app.innerHTML = empty("⚠️", esc(e.message), `<button class="btn ghost" onclick="router()">Повторить</button>`);
  }
}
window.addEventListener("hashchange", router);

async function refreshBadge() {
  try {
    const pending = await api("/api/me/responses/received", { params: { status: "pending" } });
    document.getElementById("badge").hidden = pending.length === 0;
  } catch { /* non-critical */ }
}

// ---------- views: login ----------
async function viewLogin() {
  const demo = await api("/api/auth/demo-accounts").catch(() => []);
  $app.innerHTML = `
    <div class="card stack" style="margin-top:8vh">
      <h1>Бизнес-клуб · Match</h1>
      <p class="muted">Стартапы и вакансии участников клуба. Войдите, чтобы смотреть ленту и откликаться.</p>
      <form id="login">
        <label>Email</label><input name="email" type="email" required autocomplete="username" />
        <label>Пароль</label><input name="password" type="password" required autocomplete="current-password" />
        <div class="err" id="err"></div>
        <button class="btn block" style="margin-top:14px">Войти</button>
      </form>
      ${demo.length ? `
        <div class="field-label">Тестовые аккаунты (пароль ${esc(demo[0].password)})</div>
        <div class="demo">${demo.map((d) => `
          <button data-email="${esc(d.email)}" data-pass="${esc(d.password)}">
            <b>${esc(d.full_name)}</b> <span class="muted small">· ${esc(d.headline)}</span><br/>
            <span class="small muted">${esc(d.email)}</span>
          </button>`).join("")}
        </div>` : ""}
    </div>`;
  const doLogin = async (email, password) => {
    try {
      const res = await api("/api/auth/login", { method: "POST", body: { email, password } });
      auth.set(res.token, res.user);
      location.hash = "#/feed";
    } catch (e) {
      document.getElementById("err").textContent = e.message;
    }
  };
  document.getElementById("login").onsubmit = (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    doLogin(f.get("email"), f.get("password"));
  };
  $app.querySelectorAll(".demo button").forEach((b) => (b.onclick = () => doLogin(b.dataset.email, b.dataset.pass)));
}

// ---------- views: feed ----------
const feedState = { kind: "", q: "", skill: "" };

function postCard(p) {
  const status = p.my_response
    ? badge(p.my_response.status, `Отклик: ${RESP_STATUS[p.my_response.status]}`)
    : p.is_own ? badge(p.status, POST_STATUS[p.status]) : "";
  return `
    <a class="card" href="#/post/${p.id}">
      <div class="row spread">${badge(p.kind, KIND[p.kind])}${status}</div>
      <h3 style="margin-top:8px">${esc(p.title)}</h3>
      <p class="muted">${esc(p.summary)}</p>
      ${chips(p.skills, feedState.skill)}
      <div class="meta">
        <span>${esc(p.author.full_name)}</span>
        ${p.startup ? `<span>↳ ${esc(p.startup.title)}</span>` : ""}
        ${p.stage ? `<span>${STAGE[p.stage]}</span>` : ""}
        ${p.work_format ? `<span>${FORMAT[p.work_format]}</span>` : ""}
        ${p.compensation ? `<span>${esc(p.compensation)}</span>` : ""}
        ${p.is_own ? `<span>Откликов: ${p.responses_total} (новых ${p.responses_pending})</span>` : ""}
      </div>
    </a>`;
}

async function viewFeed() {
  $app.innerHTML = `
    <h1>Лента</h1>
    <div class="segmented" id="kinds">
      ${[["", "Все"], ["startup", "Стартапы"], ["vacancy", "Вакансии"]]
        .map(([k, t]) => `<button data-kind="${k}" class="${feedState.kind === k ? "on" : ""}">${t}</button>`).join("")}
    </div>
    <input id="q" type="search" placeholder="Поиск: название, описание, навыки" value="${esc(feedState.q)}" style="margin-top:10px" />
    <div id="skillFilter"></div>
    <div id="list" class="list" style="margin-top:12px"></div>
    <div id="more" style="margin-top:12px"></div>`;

  let page = 1, items = [], seq = 0;
  const list = document.getElementById("list");
  const more = document.getElementById("more");

  async function load(reset) {
    if (reset) { page = 1; items = []; list.innerHTML = spinner(); }
    const mySeq = ++seq;
    document.getElementById("skillFilter").innerHTML = feedState.skill
      ? `<div class="row" style="margin-top:8px"><span class="small muted">Навык:</span><span class="chip on" id="clearSkill">${esc(feedState.skill)} ✕</span></div>` : "";
    const clr = document.getElementById("clearSkill");
    if (clr) clr.onclick = () => { feedState.skill = ""; load(true); };
    try {
      const data = await api("/api/posts", { params: { kind: feedState.kind, q: feedState.q, skill: feedState.skill, page, page_size: 10 } });
      if (mySeq !== seq) return; // a newer request superseded this one
      items = items.concat(data.items);
      list.innerHTML = items.length
        ? items.map(postCard).join("")
        : empty("🔍", feedState.q || feedState.kind || feedState.skill
            ? "Ничего не найдено. Попробуйте изменить фильтры."
            : "Пока нет публикаций от других участников.",
            `<a class="btn" href="#/new">Разместить свою</a>`);
      more.innerHTML = items.length < data.total
        ? `<button class="btn ghost block" id="moreBtn">Показать ещё (${data.total - items.length})</button>` : "";
      const btn = document.getElementById("moreBtn");
      if (btn) btn.onclick = () => { btn.disabled = true; page += 1; load(false); };
    } catch (e) {
      if (mySeq !== seq) return;
      list.innerHTML = empty("⚠️", esc(e.message), `<button class="btn ghost" id="retry">Повторить</button>`);
      document.getElementById("retry").onclick = () => load(true);
    }
  }

  document.getElementById("kinds").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    feedState.kind = b.dataset.kind;
    document.querySelectorAll("#kinds button").forEach((x) => x.classList.toggle("on", x === b));
    load(true);
  };
  let t;
  document.getElementById("q").oninput = (e) => {
    clearTimeout(t);
    t = setTimeout(() => { feedState.q = e.target.value.trim(); load(true); }, 300);
  };
  list.onclick = (e) => {
    const chip = e.target.closest(".chip[data-skill]");
    if (!chip) return;
    e.preventDefault();
    feedState.skill = chip.dataset.skill;
    load(true);
  };
  await load(true);
}

// ---------- views: post detail ----------
function field(label, value) {
  return value ? `<div class="field-label">${label}</div><p class="pre">${esc(value)}</p>` : "";
}

async function viewPost(m) {
  const id = +m[1];
  const p = await api(`/api/posts/${id}`);
  const vacancies = p.kind === "startup" && p.vacancies.length
    ? `<div class="field-label">Вакансии стартапа</div><div class="list">${p.vacancies
        .map((v) => `<a href="#/post/${v.id}" class="row"><span>${esc(v.title)}</span>${v.status !== "active" ? badge(v.status, POST_STATUS[v.status]) : ""}</a>`).join("")}</div>` : "";

  $app.innerHTML = `
    <div class="card">
      <div class="row spread">${badge(p.kind, KIND[p.kind])}${p.status !== "active" || p.is_own ? badge(p.status, POST_STATUS[p.status]) : ""}</div>
      <h1 style="margin-top:10px">${esc(p.title)}</h1>
      <p>${esc(p.summary)}</p>
      ${p.startup ? `<p class="small">Стартап: <a href="#/post/${p.startup.id}">${esc(p.startup.title)}</a></p>` : ""}
      ${chips(p.skills)}
      <div class="meta">
        ${p.stage ? `<span>Стадия: ${STAGE[p.stage]}</span>` : ""}
        ${p.work_format ? `<span>Формат: ${FORMAT[p.work_format]}</span>` : ""}
        ${p.compensation ? `<span>Условия: ${esc(p.compensation)}</span>` : ""}
        <span>${fmtDate(p.created_at)}</span>
      </div>
      ${field("Описание", p.description)}
      ${field(p.kind === "startup" ? "Кого ищем" : "Требования", p.looking_for)}
      ${vacancies}
      <div class="field-label">Автор</div>
      <div class="author" style="margin-top:6px">
        <div class="avatar">${esc(initials(p.author.full_name))}</div>
        <div><b>${esc(p.author.full_name)}</b><div class="small muted">${esc([p.author.headline, p.author.city].filter(Boolean).join(" · "))}</div></div>
      </div>
    </div>
    <div id="action" style="margin-top:12px"></div>`;

  const action = document.getElementById("action");
  if (p.is_own) return renderOwnerPanel(p, action);
  renderApplicantPanel(p, action);
}

function renderApplicantPanel(p, el) {
  const r = p.my_response;
  const canApply = p.status === "active" && (!r || r.status === "withdrawn");
  let html = "";
  if (r && r.status !== "withdrawn") {
    html += `<div class="card">
      <div class="row spread"><b>Ваш отклик</b>${badge(r.status, RESP_STATUS[r.status])}</div>
      ${r.status === "accepted" ? `<div class="notice ok">Автор принял отклик. Контакт для связи: <b>${esc(r.author_contact || "не указан")}</b></div>` : ""}
      ${r.status === "pending" ? `<p class="small muted">Автор увидит отклик в своём кабинете.</p><button class="btn danger sm" id="withdraw">Отозвать отклик</button>` : ""}
      ${r.status === "rejected" ? `<p class="small muted">Подробности — в разделе «Отправленные».</p>` : ""}
    </div>`;
  }
  if (canApply) {
    html += `<form class="card" id="applyForm">
      <b>${r ? "Откликнуться снова" : "Откликнуться"}</b>
      <label>Сообщение автору <span class="req">*</span></label>
      <textarea name="message" required minlength="10" maxlength="2000" placeholder="Коротко о себе и почему вам интересно"></textarea>
      <div class="hint">От 10 символов. Ваш контакт станет виден автору после того, как он примет отклик.</div>
      <div class="err" id="applyErr"></div>
      <button class="btn block" style="margin-top:10px">Отправить отклик</button>
    </form>`;
  } else if (!r && p.status !== "active") {
    html += `<div class="notice warn">Публикация ${p.status === "paused" ? "на паузе" : "закрыта"} и не принимает отклики.</div>`;
  }
  el.innerHTML = html;

  const w = document.getElementById("withdraw");
  if (w) w.onclick = async () => {
    if (!confirm("Отозвать отклик?")) return;
    w.disabled = true;
    try { await api(`/api/responses/${r.id}/withdraw`, { method: "POST" }); toast("Отклик отозван"); router(); }
    catch (e) { toast(e.message, true); w.disabled = false; }
  };
  const form = document.getElementById("applyForm");
  if (form) form.onsubmit = async (ev) => {
    ev.preventDefault();
    const btn = form.querySelector("button");
    const message = new FormData(form).get("message").trim();
    if (message.length < 10) return (document.getElementById("applyErr").textContent = "Напишите хотя бы 10 символов");
    btn.disabled = true;
    try {
      await api(`/api/posts/${p.id}/responses`, { method: "POST", body: { message } });
      haptic("success"); toast("Отклик отправлен"); router();
    } catch (e) {
      document.getElementById("applyErr").textContent = e.message;
      btn.disabled = false;
    }
  };
}

async function renderOwnerPanel(p, el) {
  const controls = p.status === "closed"
    ? `<div class="notice">Публикация закрыта. Ожидавшие отклики были автоматически отклонены.</div>`
    : `<div class="row">
        <a class="btn ghost sm" href="#/edit/${p.id}">Редактировать</a>
        <button class="btn ghost sm" data-status="${p.status === "active" ? "paused" : "active"}">${p.status === "active" ? "Поставить на паузу" : "Возобновить"}</button>
        <button class="btn danger sm" data-status="closed">Закрыть</button>
      </div>`;
  el.innerHTML = `<div class="card">${controls}</div><h2>Отклики</h2><div id="responses">${spinner()}</div>`;
  el.querySelectorAll("[data-status]").forEach((b) => (b.onclick = async () => {
    const status = b.dataset.status;
    if (status === "closed" && !confirm("Закрыть публикацию? Все ожидающие отклики будут отклонены. Это действие нельзя отменить.")) return;
    b.disabled = true;
    try { await api(`/api/posts/${p.id}`, { method: "PATCH", body: { status } }); toast("Статус обновлён"); router(); }
    catch (e) { toast(e.message, true); b.disabled = false; }
  }));
  const responses = await api(`/api/posts/${p.id}/responses`);
  renderReceived(document.getElementById("responses"), responses, { showPost: false });
}

// ---------- responses lists ----------
function receivedCard(r, showPost) {
  const a = r.applicant;
  return `<div class="card" data-id="${r.id}">
    <div class="row spread">
      <div class="author"><div class="avatar">${esc(initials(a.full_name))}</div>
        <div><b>${esc(a.full_name)}</b><div class="small muted">${esc([a.headline, a.city].filter(Boolean).join(" · "))}</div></div>
      </div>
      ${badge(r.status, RESP_STATUS[r.status])}
    </div>
    ${showPost ? `<p class="small">На: <a href="#/post/${r.post.id}">${esc(r.post.title)}</a></p>` : ""}
    <p class="pre" style="margin-top:8px">${esc(r.message)}</p>
    ${chips(a.skills)}
    <div class="meta"><span>${fmtDate(r.created_at)}</span></div>
    ${r.status === "accepted" ? `<div class="notice ok">Контакт кандидата: <b>${esc(a.contact || "не указан")}</b></div>` : ""}
    ${r.author_note ? `<p class="small muted">Ваш ответ: ${esc(r.author_note)}</p>` : ""}
    ${r.status === "pending" ? `
      <input class="note" placeholder="Комментарий кандидату (необязательно)" maxlength="1000" style="margin-top:10px" />
      <div class="row" style="margin-top:8px">
        <button class="btn ok sm" data-decide="accepted">Принять</button>
        <button class="btn danger sm" data-decide="rejected">Отклонить</button>
      </div>` : ""}
  </div>`;
}

function renderReceived(container, responses, { showPost }) {
  container.innerHTML = responses.length
    ? `<div class="list">${responses.map((r) => receivedCard(r, showPost)).join("")}</div>`
    : empty("📭", "Откликов пока нет.");
  container.querySelectorAll("[data-decide]").forEach((b) => (b.onclick = async () => {
    const card = b.closest("[data-id]");
    const status = b.dataset.decide;
    card.querySelectorAll("button").forEach((x) => (x.disabled = true));
    try {
      await api(`/api/responses/${card.dataset.id}/decision`, {
        method: "POST", body: { status, note: card.querySelector(".note").value.trim() },
      });
      haptic("success");
      toast(status === "accepted" ? "Отклик принят — контакты открыты обеим сторонам" : "Отклик отклонён");
      router();
    } catch (e) {
      toast(e.message, true);
      card.querySelectorAll("button").forEach((x) => (x.disabled = false));
    }
  }));
}

function sentCard(r) {
  return `<div class="card">
    <div class="row spread">${badge(r.post.kind, KIND[r.post.kind])}${badge(r.status, RESP_STATUS[r.status])}</div>
    <h3 style="margin-top:8px"><a href="#/post/${r.post.id}">${esc(r.post.title)}</a></h3>
    <div class="small muted">${esc(r.post.author.full_name)} · ${fmtDate(r.created_at)}${r.post.status !== "active" ? ` · публикация ${POST_STATUS[r.post.status].toLowerCase()}` : ""}</div>
    <p class="pre small" style="margin-top:6px">${esc(r.message)}</p>
    ${r.author_note ? `<div class="notice">Ответ автора: ${esc(r.author_note)}</div>` : ""}
    ${r.status === "accepted" ? `<div class="notice ok">Контакт автора: <b>${esc(r.author_contact || "не указан")}</b></div>` : ""}
  </div>`;
}

// ---------- views: cabinet ----------
async function viewCabinet(m) {
  const tab = m[1];
  const u = auth.user;
  const tabs = [["posts", "Мои публикации"], ["received", "Входящие отклики"], ["sent", "Отправленные"], ["profile", "Профиль"]];
  $app.innerHTML = `
    <div class="card author">
      <div class="avatar" style="width:48px;height:48px;font-size:18px">${esc(initials(u.full_name))}</div>
      <div style="flex:1"><h3>${esc(u.full_name)}</h3><div class="small muted">${esc(u.headline || "Заполните профиль, чтобы авторам было проще вас оценить")}</div></div>
    </div>
    <nav class="tabs">${tabs.map(([k, t]) => `<a href="#/me/${k}" class="${k === tab ? "on" : ""}">${t}</a>`).join("")}</nav>
    <div id="tab">${spinner()}</div>`;
  const el = document.getElementById("tab");

  if (tab === "posts") {
    const posts = await api("/api/me/posts");
    el.innerHTML = posts.length
      ? `<div class="list">${posts.map(postCard).join("")}</div>`
      : empty("📝", "У вас пока нет публикаций.", `<a class="btn" href="#/new">Разместить стартап или вакансию</a>`);
  } else if (tab === "sent") {
    const sent = await api("/api/me/responses/sent");
    el.innerHTML = sent.length
      ? `<div class="list">${sent.map(sentCard).join("")}</div>`
      : empty("📤", "Вы ещё никуда не откликались.", `<a class="btn" href="#/feed">Открыть ленту</a>`);
  } else if (tab === "received") {
    const filters = [["pending", "Новые"], ["accepted", "Принятые"], ["rejected", "Отклонённые"], ["", "Все"]];
    let current = "pending";
    const draw = async () => {
      el.innerHTML = `<div class="segmented">${filters.map(([k, t]) => `<button data-f="${k}" class="${k === current ? "on" : ""}">${t}</button>`).join("")}</div><div id="rl" style="margin-top:12px">${spinner()}</div>`;
      el.querySelectorAll("[data-f]").forEach((b) => (b.onclick = () => { current = b.dataset.f; draw(); }));
      const data = await api("/api/me/responses/received", { params: { status: current } });
      renderReceived(document.getElementById("rl"), data, { showPost: true });
    };
    await draw();
  } else {
    renderProfileForm(el);
  }
}

function renderProfileForm(el) {
  const u = auth.user;
  el.innerHTML = `<form class="card" id="profile">
    <label>Имя <span class="req">*</span></label><input name="full_name" required minlength="2" maxlength="120" value="${esc(u.full_name)}" />
    <label>Кратко о себе</label><input name="headline" maxlength="160" value="${esc(u.headline)}" placeholder="Например: Backend-разработчик, 6 лет в финтехе" />
    <label>Город</label><input name="city" maxlength="80" value="${esc(u.city)}" />
    <label>Навыки</label><input name="skills" value="${esc(u.skills.join(", "))}" placeholder="Python, Маркетинг, Продажи" />
    <div class="hint">Через запятую, до 15.</div>
    <label>О себе</label><textarea name="bio" maxlength="4000">${esc(u.bio)}</textarea>
    <label>Контакт для связи</label><input name="contact" maxlength="120" value="${esc(u.contact)}" placeholder="@telegram или телефон" />
    <div class="hint">Показывается другой стороне только после принятого отклика.</div>
    <div class="err" id="perr"></div>
    <button class="btn block" style="margin-top:14px">Сохранить</button>
    <button type="button" class="btn ghost block" id="logout" style="margin-top:8px">Выйти</button>
    <p class="small muted" style="margin-top:10px">Email: ${esc(u.email)}</p>
  </form>`;
  const form = document.getElementById("profile");
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    f.skills = f.skills.split(",").map((s) => s.trim()).filter(Boolean);
    const btn = form.querySelector("button");
    btn.disabled = true;
    try {
      auth.user = await api("/api/me", { method: "PATCH", body: f });
      toast("Профиль сохранён");
      router();
    } catch (e) {
      document.getElementById("perr").textContent = e.message;
      btn.disabled = false;
    }
  };
  document.getElementById("logout").onclick = async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    auth.clear();
    location.hash = "#/login";
  };
}

// ---------- views: create / edit ----------
async function viewForm(editId) {
  const [post, myPosts] = await Promise.all([
    editId ? api(`/api/posts/${editId}`) : null,
    api("/api/me/posts"),
  ]);
  if (post && !post.is_own) throw new ApiError(403, "Редактировать может только автор");
  if (post?.status === "closed") throw new ApiError(409, "Закрытую публикацию нельзя изменить");
  const p = post || { kind: "startup", skills: [] };
  const startups = myPosts.filter((x) => x.kind === "startup" && x.status !== "closed");
  const opt = (map, val, emptyLabel) =>
    `<option value="">${emptyLabel}</option>` + Object.entries(map).map(([k, t]) => `<option value="${k}" ${val === k ? "selected" : ""}>${t}</option>`).join("");

  $app.innerHTML = `
    <h1>${post ? "Редактирование" : "Новая публикация"}</h1>
    <form class="card" id="postForm" novalidate>
      ${post ? `<div>${badge(p.kind, KIND[p.kind])}</div>` : `
        <div class="segmented" id="kind">
          <button type="button" data-k="startup" class="${p.kind === "startup" ? "on" : ""}">Стартап</button>
          <button type="button" data-k="vacancy" class="${p.kind === "vacancy" ? "on" : ""}">Вакансия</button>
        </div>`}
      <div data-only="vacancy">
        <label>Стартап</label>
        <select name="startup_id">
          <option value="">Без привязки к стартапу</option>
          ${startups.map((s) => `<option value="${s.id}" ${p.startup?.id === s.id ? "selected" : ""}>${esc(s.title)}</option>`).join("")}
        </select>
        <div class="hint">Вакансию можно привязать к одному из своих стартапов.</div>
      </div>
      <label>Название <span class="req">*</span></label>
      <input name="title" maxlength="140" value="${esc(p.title)}" />
      <label>Кратко <span class="req">*</span></label>
      <textarea name="summary" maxlength="280" style="min-height:64px">${esc(p.summary)}</textarea>
      <div class="hint"><span id="sumCount">0</span>/280 — показывается в ленте</div>
      <label>Подробное описание</label>
      <textarea name="description" maxlength="8000">${esc(p.description)}</textarea>
      <label id="lfLabel">Кого ищем</label>
      <textarea name="looking_for" maxlength="4000">${esc(p.looking_for)}</textarea>
      <label>Навыки / теги</label>
      <input name="skills" value="${esc((p.skills || []).join(", "))}" placeholder="Python, B2B, Маркетинг" />
      <div class="row" style="gap:10px">
        <div style="flex:1;min-width:140px" data-only="startup"><label>Стадия</label><select name="stage">${opt(STAGE, p.stage, "Не указана")}</select></div>
        <div style="flex:1;min-width:140px"><label>Формат</label><select name="work_format">${opt(FORMAT, p.work_format, "Не указан")}</select></div>
      </div>
      <label>Условия / компенсация</label>
      <input name="compensation" maxlength="120" value="${esc(p.compensation)}" placeholder="Например: 150–200 тыс. ₽ или доля 5%" />
      <div class="err" id="ferr"></div>
      <button class="btn block" style="margin-top:14px">${post ? "Сохранить" : "Опубликовать"}</button>
    </form>`;

  const form = document.getElementById("postForm");
  let kind = p.kind;
  const syncKind = () => {
    form.querySelectorAll("[data-only]").forEach((x) => (x.hidden = x.dataset.only !== kind));
    document.getElementById("lfLabel").textContent = kind === "startup" ? "Кого ищем (команда, инвестиции, партнёры)" : "Требования к кандидату";
  };
  syncKind();
  const kindEl = document.getElementById("kind");
  if (kindEl) kindEl.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    kind = b.dataset.k;
    kindEl.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    syncKind();
  };
  const sum = form.elements.summary;
  const updCount = () => (document.getElementById("sumCount").textContent = sum.value.length);
  sum.oninput = updCount; updCount();

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    const err = document.getElementById("ferr");
    if (f.title.trim().length < 3) return (err.textContent = "Название — минимум 3 символа");
    if (f.summary.trim().length < 10) return (err.textContent = "Краткое описание — минимум 10 символов");
    const body = {
      title: f.title, summary: f.summary, description: f.description, looking_for: f.looking_for,
      skills: f.skills.split(",").map((s) => s.trim()).filter(Boolean),
      work_format: f.work_format || null, compensation: f.compensation,
    };
    if (kind === "startup") body.stage = f.stage || null;
    if (kind === "vacancy") body.startup_id = f.startup_id ? +f.startup_id : null;
    const btn = form.querySelector("button:not([type=button])");
    btn.disabled = true;
    try {
      const saved = post
        ? await api(`/api/posts/${post.id}`, { method: "PATCH", body })
        : await api("/api/posts", { method: "POST", body: { ...body, kind } });
      haptic("success");
      toast(post ? "Изменения сохранены" : "Опубликовано");
      location.hash = `#/post/${saved.id}`;
    } catch (e) {
      err.textContent = e.message;
      btn.disabled = false;
    }
  };
}

router();
