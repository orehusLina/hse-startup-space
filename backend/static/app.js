"use strict";

// ---------- labels ----------
const KIND = { startup: "Стартап", vacancy: "Вакансия" };
const STAGE = { idea: "Идея", mvp: "MVP", early_revenue: "Первая выручка", growth: "Рост" };
const FORMAT = { remote: "Удалённо", office: "Офис", hybrid: "Гибрид" };
const POST_STATUS = { active: "Активна", paused: "На паузе", closed: "Закрыта" };
const RESP_STATUS = { pending: "На рассмотрении", accepted: "Принят", rejected: "Отклонён", withdrawn: "Отозван" };
const STAGE_EMOJI = { idea: "💡", mvp: "🛠️", early_revenue: "📈", growth: "🚀" };

// HSE Business Club palette: blues #6194ff → #1f3e8c, yellow accent #fff705.
const GRADS = {
  startup: [
    "linear-gradient(135deg,#6194ff,#1f3e8c)",
    "linear-gradient(135deg,#2363e7,#131b3a)",
    "linear-gradient(135deg,#5383e5,#2e4885)",
    "linear-gradient(135deg,#4582de,#19264e)",
  ],
  vacancy: [
    "linear-gradient(135deg,#fff705,#f2c200)",
    "linear-gradient(135deg,#fff705,#9fd8ff)",
    "linear-gradient(135deg,#ffe95c,#ffb800)",
  ],
  people: [
    "linear-gradient(135deg,#6194ff,#1f3e8c)", "linear-gradient(135deg,#2363e7,#19264e)",
    "linear-gradient(135deg,#5383e5,#131b3a)", "linear-gradient(135deg,#3f61ae,#06081c)",
    "linear-gradient(135deg,#4582de,#2e4885)",
  ],
};
const AVATAR_EMOJI = ["🚀", "💼", "🧑‍💻", "👩‍💼", "👨‍💼", "🎨", "📈", "💡", "🌱", "📣", "🦄", "🔥",
  "⚡", "🎯", "🧠", "🛠️", "🏆", "💎", "🌍", "🎓", "🤝", "🦊", "🐼", "😎"];

// ---------- utils ----------
const $app = document.getElementById("app");
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// FNV-1a: spreads short similar strings (names, ids) across palette entries.
const hash = (s) => [...String(s)].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261);
const pick = (arr, key) => arr[hash(key) % arr.length];
const postGrad = (p) => pick(GRADS[p.kind], p.id);
const postEmoji = (p) => (p.kind === "vacancy" ? "💼" : STAGE_EMOJI[p.stage] || "🚀");
const initials = (name) => name.split(/\s+/).map((x) => x[0]).join("").slice(0, 2).toUpperCase();
/** Avatar for a user object: Telegram photo → chosen emoji → initials, on a brand gradient.
 *  The photo sits on top of the fallback, so a broken image just reveals the emoji/initials. */
function avatar(u, cls = "") {
  const fallback = u.avatar_emoji ? esc(u.avatar_emoji) : esc(initials(u.full_name));
  const photo = u.photo_url?.startsWith("https://")
    ? `<img src="${esc(u.photo_url)}" alt="" loading="lazy" onerror="this.remove()" />` : "";
  return `<div class="avatar ${cls} ${u.avatar_emoji ? "emoji" : ""}" style="background:${pick(GRADS.people, u.full_name)}">${fallback}${photo}</div>`;
}
const svg = (id, cls = "ico") => `<svg class="${cls}"><use href="#i-${id}"/></svg>`;
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
};
function timeAgo(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "только что";
  if (s < 3600) { const m = Math.floor(s / 60); return `${m} ${plural(m, "минуту", "минуты", "минут")} назад`; }
  if (s < 86400) { const h = Math.floor(s / 3600); return `${h} ${plural(h, "час", "часа", "часов")} назад`; }
  const d = Math.floor(s / 86400);
  if (d === 1) return "вчера";
  if (d < 30) return `${d} ${plural(d, "день", "дня", "дней")} назад`;
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}
const badge = (cls, text) => `<span class="badge b-${esc(cls)}">${esc(text)}</span>`;
const chips = (skills, active) =>
  skills?.length
    ? `<div class="chips">${skills
        .map((s) => `<span class="chip ${active && s.toLowerCase() === active.toLowerCase() ? "on" : ""}" data-skill="${esc(s)}">${esc(s)}</span>`)
        .join("")}</div>`
    : "";
const skeleton = (n = 3) =>
  `<div class="list">${Array.from({ length: n }, (_, i) => `
    <div class="skel rise" style="--i:${i}"><div class="row"><i class="t"></i><div class="grow"><i style="width:40%;margin:0"></i><i style="width:60%"></i></div></div>
    <i style="width:85%;margin-top:16px"></i><i style="width:65%"></i></div>`).join("")}</div>`;
const empty = (art, title, text, action = "") =>
  `<div class="empty rise"><div class="art">${art}</div><h3>${title}</h3><p>${text}</p>${action}</div>`;

let toastTimer;
function toast(text, isError = false) {
  const el = document.getElementById("toast");
  el.innerHTML = `<span>${isError ? "⚠️" : "✨"}</span><span>${esc(text)}</span>`;
  el.className = `toast show ${isError ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 2800);
}

/** Bottom sheet. `build(close)` returns HTML and wires handlers via the returned element. */
function openSheet(html, onMount) {
  const wrap = document.createElement("div");
  wrap.className = "sheet-wrap";
  wrap.innerHTML = `<div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>${html}</div>`;
  const close = () => { wrap.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => e.key === "Escape" && close();
  wrap.addEventListener("click", (e) => e.target === wrap && close());
  document.addEventListener("keydown", onKey);
  document.body.appendChild(wrap);
  onMount(wrap, close);
  return close;
}

// ---------- Telegram ----------
const tg = window.Telegram?.WebApp;
if (tg?.initData) {
  document.documentElement.classList.add("tg");
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.("#06081c");
  tg.setBackgroundColor?.("#06081c");
  tg.BackButton.onClick(() => history.back());
}
const haptic = (type) => tg?.HapticFeedback?.notificationOccurred?.(type);
const tap = () => tg?.HapticFeedback?.impactOccurred?.("light");

/** "@username" → link that opens the chat (inside Telegram without leaving the app). */
function contactAction(contact) {
  const m = /^@?([A-Za-z0-9_]{5,32})$/.exec((contact || "").trim());
  if (!m) return "";
  return `<a class="btn sm ok" href="https://t.me/${m[1]}" target="_blank" data-tglink="https://t.me/${m[1]}">${svg("send", "ico-sm")} Написать</a>`;
}
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-tglink]");
  if (a && tg?.openTelegramLink) { e.preventDefault(); tg.openTelegramLink(a.dataset.tglink); }
});

// Inside Telegram the user is identified by signed initData, no password needed.
let tgLoginError = "";
async function telegramLogin() {
  try {
    const res = await api("/api/auth/telegram", { method: "POST", body: { init_data: tg.initData } });
    auth.set(res.token, res.user);
    tgLoginError = "";
    return true;
  } catch (e) {
    tgLoginError = e.message;
    return false;
  }
}

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
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
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
  [/^#\/new$/, () => viewForm(null), { tab: "new" }],
  [/^#\/edit\/(\d+)$/, (m) => viewForm(+m[1]), { tab: "me", back: true }],
  [/^#\/me\/(profile|posts|sent|received)$/, viewCabinet, { tab: "me" }],
];

async function router() {
  const hash = location.hash || "#/feed";
  const match = routes.find(([re]) => re.test(hash));
  if (!match) return (location.hash = "#/feed");
  const [re, view, opts] = match;

  if (!opts.public && !auth.token) {
    if (!(tg?.initData && !tgLoginError && (await telegramLogin()))) return (location.hash = "#/login");
  }
  if (!opts.public && !auth.user) {
    try { auth.user = await api("/api/me"); } catch { return; }
  }
  document.querySelectorAll(".sheet-wrap").forEach((s) => s.remove());
  document.body.classList.toggle("auth", !!opts.public);
  document.getElementById("topbar").hidden = !!opts.public;
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.tab === opts.tab));
  if (tg) opts.back ? tg.BackButton.show() : tg.BackButton.hide();
  if (!opts.public) refreshBadge();

  $app.innerHTML = skeleton();
  window.scrollTo(0, 0);
  try {
    await view(hash.match(re));
  } catch (e) {
    if (e.status === 401) return;
    $app.innerHTML = empty("😵", "Что-то пошло не так", esc(e.message), `<button class="btn" onclick="router()">Повторить</button>`);
  }
}
window.addEventListener("hashchange", router);

let pendingCount = 0;
async function refreshBadge() {
  try {
    pendingCount = (await api("/api/me/responses/received", { params: { status: "pending" } })).length;
    document.getElementById("badge").hidden = pendingCount === 0;
  } catch { /* non-critical */ }
}

// ---------- views: login ----------
async function viewLogin() {
  const demo = await api("/api/auth/demo-accounts").catch(() => []);
  $app.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-head rise">
        <div class="logo">✦</div>
        <div class="eyebrow">Бизнес-клуб ВШЭ</div>
        <h1>Startup <span>Space</span></h1>
        <p>Стартапы и вакансии резидентов крупнейшего студенческого бизнес-клуба России.<br/>Находите команду, проекты и партнёров.</p>
      </div>
      <div class="glass rise" style="--i:2">
        ${tg?.initData ? `
          <button class="btn block lg" id="tgLogin">Войти через Telegram</button>
          <div class="err">${esc(tgLoginError)}</div>
          <div class="or">или по email</div>` : ""}
        <form id="login">
          <label>Email</label><input name="email" type="email" required autocomplete="username" placeholder="you@club.test" />
          <label>Пароль</label><input name="password" type="password" required autocomplete="current-password" placeholder="••••••••" />
          <div class="err" id="err"></div>
          <button class="btn block lg" style="margin-top:18px">Войти</button>
        </form>
        ${demo.length ? `
          <div class="or">тестовые аккаунты · пароль ${esc(demo[0].password)}</div>
          <div class="demo">${demo.map((d, i) => `
            <button class="rise" style="--i:${i + 3}" data-email="${esc(d.email)}" data-pass="${esc(d.password)}">
              ${avatar(d)}
              <span class="grow"><b>${esc(d.full_name)}</b><br/><span class="small muted">${esc(d.headline)}</span></span>
              ${svg("chev", "ico-sm chev")}
            </button>`).join("")}
          </div>` : ""}
      </div>
    </div>`;
  const doLogin = async (email, password) => {
    try {
      const res = await api("/api/auth/login", { method: "POST", body: { email, password } });
      auth.set(res.token, res.user);
      haptic("success");
      location.hash = "#/feed";
    } catch (e) {
      document.getElementById("err").textContent = e.message;
      haptic("error");
    }
  };
  document.getElementById("login").onsubmit = (ev) => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    doLogin(f.get("email"), f.get("password"));
  };
  const tgBtn = document.getElementById("tgLogin");
  if (tgBtn) tgBtn.onclick = async () => {
    tgBtn.disabled = true;
    if (await telegramLogin()) location.hash = "#/feed";
    else viewLogin();
  };
  $app.querySelectorAll(".demo button").forEach((b) => (b.onclick = () => doLogin(b.dataset.email, b.dataset.pass)));
}

// ---------- views: feed ----------
const feedState = { kind: "", q: "", skill: "" };

function postCard(p, i = 0) {
  const status = p.my_response
    ? badge(p.my_response.status, RESP_STATUS[p.my_response.status])
    : p.is_own && p.status !== "active" ? badge(p.status, POST_STATUS[p.status]) : "";
  const sub = [KIND[p.kind], p.stage && STAGE[p.stage]].filter(Boolean).join(" · ");
  return `
    <a class="pcard ${p.kind} rise" style="--i:${i}" href="#/post/${p.id}">
      <div class="phead">
        <div class="tile" style="background:${postGrad(p)}">${postEmoji(p)}</div>
        <div class="grow">
          <div class="kindline">${esc(sub)}</div>
          <div class="byline">${esc(p.author.full_name)}${p.startup ? ` · ${esc(p.startup.title)}` : ""}</div>
        </div>
        ${status}
      </div>
      <h3>${esc(p.title)}</h3>
      <p class="clamp2">${esc(p.summary)}</p>
      ${chips(p.skills.slice(0, 5), feedState.skill)}
      <div class="pfoot">
        ${p.compensation ? `<span class="pill-meta money">💰 ${esc(p.compensation)}</span>` : ""}
        ${p.work_format ? `<span class="pill-meta">📍 ${FORMAT[p.work_format]}</span>` : ""}
        ${p.is_own ? `<span class="pill-meta">📨 ${p.responses_total} · новых ${p.responses_pending}</span>` : ""}
        <span class="ago">${timeAgo(p.created_at)}</span>
      </div>
    </a>`;
}

function mountSegmented(root, onChange) {
  const pill = root.querySelector(".pill");
  const place = () => {
    const on = root.querySelector("button.on");
    if (!on) return;
    pill.style.width = `${on.offsetWidth}px`;
    pill.style.transform = `translateX(${on.offsetLeft - 4}px)`;
  };
  root.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b || b.classList.contains("on")) return;
    root.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    place(); tap();
    onChange(b.dataset.v);
  });
  requestAnimationFrame(place);
  window.addEventListener("resize", place);
}

async function viewFeed() {
  const firstName = auth.user.full_name.split(" ")[0];
  $app.innerHTML = `
    <section class="hero rise">
      <div class="eyebrow">HSE Business Club</div>
      <div class="hello" style="margin-top:10px">Привет, ${esc(firstName)} 👋</div>
      <h1>Найди <em>команду</em> для своего дела</h1>
      <div class="stats">
        <button class="stat" data-k="startup"><b id="nStartups">·</b><span id="lStartups">стартапов</span></button>
        <button class="stat" data-k="vacancy"><b id="nVacancies">·</b><span id="lVacancies">вакансий</span></button>
        <a class="stat ${pendingCount ? "hot" : ""}" href="#/me/received"><b id="nPending">${pendingCount}</b><span>${plural(pendingCount, "входящий", "входящих", "входящих")}</span></a>
      </div>
    </section>
    <div class="toolbar">
      <div class="search">${svg("search")}<input id="q" type="search" placeholder="Поиск по названию, описанию, навыкам" value="${esc(feedState.q)}" /></div>
      <div class="seg" id="kinds"><span class="pill"></span>
        ${[["", "Все"], ["startup", "🚀 Стартапы"], ["vacancy", "💼 Вакансии"]]
          .map(([k, t]) => `<button data-v="${k}" class="${feedState.kind === k ? "on" : ""}">${t}</button>`).join("")}
      </div>
      <div id="skillFilter"></div>
    </div>
    <div id="list"></div>
    <div id="more" style="margin-top:14px"></div>`;

  // hero counters (cheap: page_size=1, we only need totals)
  Promise.all(["startup", "vacancy"].map((kind) => api("/api/posts", { params: { kind, page_size: 1 } })))
    .then(([s, v]) => {
      document.getElementById("nStartups").textContent = s.total;
      document.getElementById("lStartups").textContent = plural(s.total, "стартап", "стартапа", "стартапов");
      document.getElementById("nVacancies").textContent = v.total;
      document.getElementById("lVacancies").textContent = plural(v.total, "вакансия", "вакансии", "вакансий");
    }).catch(() => {});

  let page = 1, items = [], seq = 0;
  const list = document.getElementById("list");
  const more = document.getElementById("more");
  const kinds = document.getElementById("kinds");

  async function load(reset) {
    if (reset) { page = 1; items = []; list.innerHTML = skeleton(); }
    const mySeq = ++seq;
    document.getElementById("skillFilter").innerHTML = feedState.skill
      ? `<button class="filter-chip" id="clearSkill"># ${esc(feedState.skill)} ${svg("x", "ico-sm")}</button>` : "";
    const clr = document.getElementById("clearSkill");
    if (clr) clr.onclick = () => { feedState.skill = ""; load(true); };
    try {
      const data = await api("/api/posts", { params: { kind: feedState.kind, q: feedState.q, skill: feedState.skill, page, page_size: 10 } });
      if (mySeq !== seq) return; // a newer request superseded this one
      items = items.concat(data.items);
      if (!items.length) {
        list.innerHTML = feedState.q || feedState.kind || feedState.skill
          ? empty("🔭", "Ничего не нашлось", "Попробуйте другой запрос или сбросьте фильтры.")
          : empty("🌱", "Здесь пока пусто", "Станьте первым — разместите стартап или вакансию.", `<a class="btn" href="#/new">${svg("plus", "ico-sm")} Разместить</a>`);
      } else if (reset) {
        list.innerHTML = `<div class="list">${items.map((p, i) => postCard(p, i)).join("")}</div>`;
      } else {
        list.querySelector(".list").insertAdjacentHTML("beforeend", data.items.map((p, i) => postCard(p, i)).join(""));
      }
      more.innerHTML = items.length < data.total
        ? `<button class="btn ghost block" id="moreBtn">Показать ещё · ${data.total - items.length}</button>` : "";
      const btn = document.getElementById("moreBtn");
      if (btn) btn.onclick = () => { btn.disabled = true; page += 1; load(false); };
    } catch (e) {
      if (mySeq !== seq) return;
      list.innerHTML = empty("📡", "Не удалось загрузить", esc(e.message), `<button class="btn ghost" id="retry">Повторить</button>`);
      document.getElementById("retry").onclick = () => load(true);
    }
  }

  mountSegmented(kinds, (v) => { feedState.kind = v; load(true); });
  $app.querySelectorAll(".stat[data-k]").forEach((b) => (b.onclick = () => {
    kinds.querySelector(`button[data-v="${b.dataset.k}"]`).click();
  }));
  let t;
  document.getElementById("q").oninput = (e) => {
    clearTimeout(t);
    t = setTimeout(() => { feedState.q = e.target.value.trim(); load(true); }, 300);
  };
  list.onclick = (e) => {
    const chip = e.target.closest(".chip[data-skill]");
    if (!chip) return;
    e.preventDefault();
    tap();
    feedState.skill = chip.dataset.skill;
    load(true);
  };
  await load(true);
}

// ---------- views: post detail ----------
function textSection(title, value, i) {
  return value ? `<div class="card rise" style="--i:${i}"><div class="section-title">${title}</div><p class="pre">${esc(value)}</p></div>` : "";
}

async function viewPost(m) {
  const id = +m[1];
  const p = await api(`/api/posts/${id}`);
  const facts = [
    p.stage && ["🧭", "Стадия", STAGE[p.stage]],
    p.work_format && ["📍", "Формат", FORMAT[p.work_format]],
    p.compensation && ["💰", "Условия", p.compensation],
    ["🗓️", "Опубликовано", timeAgo(p.created_at)],
  ].filter(Boolean);
  const vacancies = p.kind === "startup" && p.vacancies.length
    ? `<div class="card rise" style="--i:5"><div class="section-title">Открытые вакансии · ${p.vacancies.length}</div>
        ${p.vacancies.map((v) => `<a class="linked" href="#/post/${v.id}">
          <div class="tile" style="width:38px;height:38px;font-size:18px;background:${pick(GRADS.vacancy, v.id)}">💼</div>
          <b class="grow">${esc(v.title)}</b>${v.status !== "active" ? badge(v.status, POST_STATUS[v.status]) : ""}${svg("chev", "ico-sm chev")}</a>`).join("")}
      </div>` : "";

  $app.innerHTML = `
    <section class="cover ${p.kind} rise" style="background:${postGrad(p)}">
      <a class="back" href="javascript:history.back()" aria-label="Назад">${svg("back")}</a>
      <div class="big-emoji">${postEmoji(p)}</div>
      <span class="kind-pill">${KIND[p.kind]}${p.status !== "active" ? ` · ${POST_STATUS[p.status]}` : ""}</span>
      <h1>${esc(p.title)}</h1>
      <div class="sub">${esc(p.summary)}</div>
    </section>
    <div class="facts">${facts.map(([e, k, v], i) => `<div class="fact rise" style="--i:${i + 1}"><div class="k">${e} ${k}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>
    ${p.startup ? `<a class="card rise linked" style="--i:2;margin-top:12px;display:flex" href="#/post/${p.startup.id}">
        <div class="tile" style="width:38px;height:38px;font-size:18px;background:${pick(GRADS.startup, p.startup.id)}">🚀</div>
        <div class="grow"><div class="small muted">Вакансия стартапа</div><b>${esc(p.startup.title)}</b></div>${svg("chev", "ico-sm chev")}</a>` : ""}
    <div style="margin-top:12px">
      ${p.skills.length ? `<div class="card rise ${p.kind}" style="--i:3;--accent:var(--${p.kind})"><div class="section-title">Навыки</div>${chips(p.skills)}</div>` : ""}
      ${textSection("О проекте", p.description, 4)}
      ${textSection(p.kind === "startup" ? "Кого ищем" : "Требования", p.looking_for, 5)}
      ${vacancies}
      <div class="card rise" style="--i:6"><div class="section-title">Автор</div>
        <div class="person">${avatar(p.author)}
          <div class="grow"><b>${esc(p.author.full_name)}</b><div class="small muted">${esc([p.author.headline, p.author.city].filter(Boolean).join(" · "))}</div></div>
        </div>
        ${p.author.bio ? `<p class="small muted" style="margin-top:10px">${esc(p.author.bio)}</p>` : ""}
      </div>
    </div>
    <div id="action"></div>`;

  const action = document.getElementById("action");
  if (p.is_own) return renderOwnerPanel(p, action);
  renderApplicantPanel(p, action);
}

function steps(status) {
  const decided = status === "accepted" || status === "rejected";
  const last = status === "accepted" ? ["ok", "✓", "Принят"] : status === "rejected" ? ["bad", "✕", "Отклонён"] : ["", "3", "Решение"];
  return `<div class="steps">
    <div class="step done"><i>✓</i>Отправлен</div><div class="bar done"></div>
    <div class="step done"><i>${decided ? "✓" : "…"}</i>Рассмотрение</div><div class="bar ${decided ? "done" : ""}"></div>
    <div class="step ${last[0]}"><i>${last[1]}</i>${last[2]}</div>
  </div>`;
}

function renderApplicantPanel(p, el) {
  const r = p.my_response;
  const canApply = p.status === "active" && (!r || r.status === "withdrawn");
  let html = "";
  if (r && r.status !== "withdrawn") {
    html += `<div class="card rise" style="--i:7;margin-top:12px">
      <div class="row spread"><h3>Ваш отклик</h3>${badge(r.status, RESP_STATUS[r.status])}</div>
      ${steps(r.status)}
      ${r.status === "accepted" ? `<div class="reveal"><span class="e">🤝</span><div class="grow"><span class="small muted">Контакт автора</span><b>${esc(r.author_contact || "не указан")}</b></div>${contactAction(r.author_contact)}</div>` : ""}
      ${r.status === "pending" ? `<p class="small muted" style="margin-top:12px">Автор увидит отклик в своём кабинете. Контакты откроются, когда он примет решение.</p>
        <button class="btn danger sm" id="withdraw" style="margin-top:6px">Отозвать отклик</button>` : ""}
      ${r.status === "rejected" ? `<p class="small muted" style="margin-top:12px">Не расстраивайтесь — в ленте много других проектов.</p>` : ""}
    </div>`;
  }
  if (canApply) {
    html += `<div class="cta-bar rise" style="--i:7"><button class="btn block lg" id="applyBtn">${svg("send", "ico-sm")} ${r ? "Откликнуться снова" : "Откликнуться"}</button></div>`;
  } else if (!r && p.status !== "active") {
    html += `<div class="notice warn">Публикация ${p.status === "paused" ? "на паузе" : "закрыта"} и сейчас не принимает отклики.</div>`;
  }
  el.innerHTML = html;

  const w = document.getElementById("withdraw");
  if (w) w.onclick = async () => {
    if (!confirm("Отозвать отклик?")) return;
    w.disabled = true;
    try { await api(`/api/responses/${r.id}/withdraw`, { method: "POST" }); toast("Отклик отозван"); router(); }
    catch (e) { toast(e.message, true); w.disabled = false; }
  };
  const applyBtn = document.getElementById("applyBtn");
  if (applyBtn) applyBtn.onclick = () => { tap(); openApplySheet(p); };
}

function openApplySheet(p) {
  openSheet(`
    <div class="person"><div class="tile" style="background:${postGrad(p)}">${postEmoji(p)}</div>
      <div class="grow"><div class="small muted">Отклик на ${KIND[p.kind].toLowerCase()}</div><h3>${esc(p.title)}</h3></div></div>
    <form id="applyForm">
      <label>Сообщение автору <span class="req">*</span></label>
      <textarea name="message" maxlength="2000" placeholder="Коротко о себе: опыт, чем можете помочь проекту, почему вам интересно" autofocus></textarea>
      <div class="hint"><span id="cnt">0</span>/2000 · минимум 10 символов. Ваш контакт автор увидит только после того, как примет отклик.</div>
      <div class="err" id="applyErr"></div>
      <button class="btn block lg" style="margin-top:16px">${svg("send", "ico-sm")} Отправить отклик</button>
    </form>`, (root, close) => {
    const form = root.querySelector("#applyForm");
    const ta = form.elements.message;
    ta.oninput = () => (root.querySelector("#cnt").textContent = ta.value.length);
    setTimeout(() => ta.focus(), 50);
    form.onsubmit = async (ev) => {
      ev.preventDefault();
      const message = ta.value.trim();
      const err = root.querySelector("#applyErr");
      if (message.length < 10) { err.textContent = "Напишите хотя бы пару предложений — от 10 символов"; haptic("error"); return; }
      const btn = form.querySelector("button");
      btn.disabled = true;
      try {
        await api(`/api/posts/${p.id}/responses`, { method: "POST", body: { message } });
        haptic("success"); close(); toast("Отклик отправлен — ждём ответа автора"); router();
      } catch (e) {
        err.textContent = e.message; btn.disabled = false; haptic("error");
      }
    };
  });
}

async function renderOwnerPanel(p, el) {
  const controls = p.status === "closed"
    ? `<div class="notice">Публикация закрыта. Ожидавшие отклики были автоматически отклонены.</div>`
    : `<div class="row" style="margin-top:12px">
        <a class="btn ghost sm" href="#/edit/${p.id}">✏️ Редактировать</a>
        <button class="btn ghost sm" data-status="${p.status === "active" ? "paused" : "active"}">${p.status === "active" ? "⏸ На паузу" : "▶️ Возобновить"}</button>
        <button class="btn danger sm" data-status="closed">Закрыть</button>
      </div>`;
  el.innerHTML = `
    <div class="card rise" style="--i:7;margin-top:12px">
      <div class="row spread"><h3>Управление</h3>${badge(p.status, POST_STATUS[p.status])}</div>
      <div class="stats" style="margin-top:12px">
        <div class="fact grow"><div class="k">📨 Всего откликов</div><div class="v">${p.responses_total}</div></div>
        <div class="fact grow"><div class="k">✨ Новых</div><div class="v">${p.responses_pending}</div></div>
      </div>
      ${controls}
    </div>
    <h2>Отклики</h2><div id="responses">${skeleton(2)}</div>`;
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
function receivedCard(r, showPost, i) {
  const a = r.applicant;
  return `<div class="card rise" style="--i:${i}" data-id="${r.id}">
    <div class="person">${avatar(a)}
      <div class="grow"><b>${esc(a.full_name)}</b><div class="small muted">${esc([a.headline, a.city].filter(Boolean).join(" · ") || "Резидент клуба")}</div></div>
    </div>
    <div class="row spread" style="margin-top:10px">
      ${showPost ? `<a class="small grow" href="#/post/${r.post.id}">→ ${esc(r.post.title)}</a>` : "<span></span>"}
      ${badge(r.status, RESP_STATUS[r.status])}
    </div>
    <div class="bubble"><div class="who">${timeAgo(r.created_at)}</div><div class="pre">${esc(r.message)}</div></div>
    ${chips(a.skills)}
    ${r.author_note ? `<div class="bubble author"><div class="who">Ваш ответ</div>${esc(r.author_note)}</div>` : ""}
    ${r.status === "accepted" ? `<div class="reveal"><span class="e">🤝</span><div class="grow"><span class="small muted">Контакт кандидата</span><b>${esc(a.contact || "не указан")}</b></div>${contactAction(a.contact)}</div>` : ""}
    ${r.status === "pending" ? `
      <input class="note" placeholder="Комментарий кандидату (необязательно)" maxlength="1000" style="margin-top:12px" />
      <div class="decide">
        <button class="btn ok" data-decide="accepted">✓ Принять</button>
        <button class="btn danger" data-decide="rejected">Отклонить</button>
      </div>` : ""}
  </div>`;
}

function renderReceived(container, responses, { showPost }) {
  container.innerHTML = responses.length
    ? `<div class="list">${responses.map((r, i) => receivedCard(r, showPost, i)).join("")}</div>`
    : empty("📭", "Откликов пока нет", "Как только кто-то откликнется, он появится здесь.");
  container.querySelectorAll("[data-decide]").forEach((b) => (b.onclick = async () => {
    const card = b.closest("[data-id]");
    const status = b.dataset.decide;
    card.querySelectorAll("button").forEach((x) => (x.disabled = true));
    try {
      await api(`/api/responses/${card.dataset.id}/decision`, {
        method: "POST", body: { status, note: card.querySelector(".note").value.trim() },
      });
      haptic("success");
      toast(status === "accepted" ? "Отклик принят — контакты открыты обеим сторонам 🤝" : "Отклик отклонён");
      router();
    } catch (e) {
      toast(e.message, true);
      card.querySelectorAll("button").forEach((x) => (x.disabled = false));
    }
  }));
}

function sentCard(r, i) {
  const fake = { id: r.post.id, kind: r.post.kind, stage: null };
  return `<div class="card rise" style="--i:${i}">
    <a class="person" href="#/post/${r.post.id}" style="color:inherit">
      <div class="tile" style="background:${postGrad(fake)}">${postEmoji(fake)}</div>
      <div class="grow"><b>${esc(r.post.title)}</b><div class="small muted">${esc(r.post.author.full_name)} · ${timeAgo(r.created_at)}${r.post.status !== "active" ? ` · ${POST_STATUS[r.post.status].toLowerCase()}` : ""}</div></div>
      ${badge(r.status, RESP_STATUS[r.status])}
    </a>
    ${r.status !== "withdrawn" ? steps(r.status) : ""}
    <div class="bubble"><div class="who">Ваше сообщение</div><div class="pre">${esc(r.message)}</div></div>
    ${r.author_note ? `<div class="bubble author"><div class="who">Ответ автора</div>${esc(r.author_note)}</div>` : ""}
    ${r.status === "accepted" ? `<div class="reveal"><span class="e">🤝</span><div class="grow"><span class="small muted">Контакт автора</span><b>${esc(r.author_contact || "не указан")}</b></div>${contactAction(r.author_contact)}</div>` : ""}
  </div>`;
}

// ---------- views: cabinet ----------
async function viewCabinet(m) {
  const tab = m[1];
  const u = auth.user;
  const [myPosts, sent] = await Promise.all([api("/api/me/posts"), api("/api/me/responses/sent")]);
  const tabs = [
    ["posts", "Публикации", myPosts.length, false],
    ["received", "Входящие", pendingCount, pendingCount > 0],
    ["sent", "Мои отклики", sent.length, false],
    ["profile", "Профиль", null, false],
  ];
  $app.innerHTML = `
    <section class="profile-hero rise">
      <div class="person"><button class="avatar-edit" id="avatarEdit" aria-label="Сменить аватар">${avatar(u, "lg")}</button>
        <div class="grow"><h1>${esc(u.full_name)}</h1><div class="sub">${esc(u.headline || "Расскажите о себе в профиле — так авторам проще вас оценить")}</div></div>
      </div>
      ${u.skills.length ? `<div class="chips" style="margin-top:14px">${u.skills.map((s) => `<span class="chip" style="background:rgba(255,255,255,.18);color:#fff">${esc(s)}</span>`).join("")}</div>` : ""}
    </section>
    <nav class="tabbar">${tabs.map(([k, t, n, hot]) =>
      `<a href="#/me/${k}" class="${k === tab ? "on" : ""}">${t}${n !== null ? `<span class="n ${hot ? "hot" : ""}">${n}</span>` : ""}</a>`).join("")}</nav>
    <div id="tab" style="margin-top:8px"></div>`;
  const el = document.getElementById("tab");
  document.getElementById("avatarEdit").onclick = () => { tap(); openAvatarPicker(); };

  if (tab === "posts") {
    el.innerHTML = myPosts.length
      ? `<div class="list">${myPosts.map((p, i) => postCard(p, i)).join("")}</div>`
      : empty("📝", "Нет публикаций", "Расскажите о своём стартапе или найдите человека в команду.", `<a class="btn" href="#/new">${svg("plus", "ico-sm")} Разместить</a>`);
  } else if (tab === "sent") {
    el.innerHTML = sent.length
      ? `<div class="list">${sent.map((r, i) => sentCard(r, i)).join("")}</div>`
      : empty("🚀", "Вы ещё не откликались", "Загляните в ленту — там проекты, которым нужны люди.", `<a class="btn" href="#/feed">Открыть ленту</a>`);
  } else if (tab === "received") {
    const filters = [["pending", "Новые"], ["accepted", "Принятые"], ["rejected", "Отклонённые"], ["", "Все"]];
    el.innerHTML = `<div class="seg" id="rf" style="margin-top:0"><span class="pill"></span>${filters.map(([k, t], i) => `<button data-v="${k}" class="${i === 0 ? "on" : ""}">${t}</button>`).join("")}</div><div id="rl" style="margin-top:12px"></div>`;
    const draw = async (status) => {
      const rl = document.getElementById("rl");
      rl.innerHTML = skeleton(2);
      renderReceived(rl, await api("/api/me/responses/received", { params: { status } }), { showPost: true });
    };
    mountSegmented(document.getElementById("rf"), draw);
    await draw("pending");
  } else {
    renderProfileForm(el);
  }
}

function openAvatarPicker() {
  const u = auth.user;
  openSheet(`
    <h3>Аватар</h3>
    <p class="small muted">${u.photo_url ? "Сейчас показывается фото из Telegram. Эмодзи будет виден, если фото недоступно." : "Выберите эмодзи — так вас проще узнать в ленте и откликах."}</p>
    <div class="emoji-grid" style="margin-top:14px">
      ${AVATAR_EMOJI.map((e) => `<button type="button" data-e="${e}" class="${u.avatar_emoji === e ? "on" : ""}">${e}</button>`).join("")}
    </div>
    <button type="button" class="btn ghost block" data-e="" style="margin-top:14px">Без эмодзи — инициалы</button>`,
  (root, close) => {
    root.querySelectorAll("[data-e]").forEach((b) => (b.onclick = async () => {
      try {
        auth.user = await api("/api/me", { method: "PATCH", body: { avatar_emoji: b.dataset.e } });
        haptic("success"); close(); toast("Аватар обновлён"); router();
      } catch (e) { toast(e.message, true); }
    }));
  });
}

function renderProfileForm(el) {
  const u = auth.user;
  el.innerHTML = `<form class="card rise" id="profile">
    <label style="margin-top:0">Имя <span class="req">*</span></label><input name="full_name" required minlength="2" maxlength="120" value="${esc(u.full_name)}" />
    <label>Кратко о себе</label><input name="headline" maxlength="160" value="${esc(u.headline)}" placeholder="Например: Backend-разработчик, 6 лет в финтехе" />
    <label>Город</label><input name="city" maxlength="80" value="${esc(u.city)}" />
    <label>Навыки</label><input name="skills" value="${esc(u.skills.join(", "))}" placeholder="Python, Маркетинг, Продажи" />
    <div class="hint">Через запятую, до 15 — по ним вас найдут авторы.</div>
    <label>О себе</label><textarea name="bio" maxlength="4000" placeholder="Опыт, проекты, чем можете быть полезны">${esc(u.bio)}</textarea>
    <label>Контакт для связи</label><input name="contact" maxlength="120" value="${esc(u.contact)}" placeholder="@telegram или телефон" />
    <div class="hint">🔒 Виден другой стороне только после принятого отклика.</div>
    <div class="err" id="perr"></div>
    <button class="btn block lg" style="margin-top:18px">Сохранить</button>
    <button type="button" class="btn ghost block" id="logout" style="margin-top:10px">Выйти</button>
    <p class="small muted" style="margin-top:12px;text-align:center">${u.telegram_id ? "Вход через Telegram" : `Email: ${esc(u.email)}`}</p>
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
      haptic("success"); toast("Профиль сохранён"); router();
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
    <div class="rise" style="margin:6px 0 14px"><h1>${post ? "Редактирование" : "Новая публикация"}</h1>
      <p class="muted">${post ? esc(p.title) : "Расскажите, что вы делаете и кого ищете — это займёт пару минут."}</p></div>
    <form id="postForm" novalidate>
      ${post ? "" : `
        <div class="kind-pick rise" id="kind" style="--i:1">
          <button type="button" data-k="startup" class="${p.kind === "startup" ? "on" : ""}"><span class="e">🚀</span><b>Стартап</b><small>Ищу команду, партнёров, инвестиции</small></button>
          <button type="button" data-k="vacancy" class="${p.kind === "vacancy" ? "on" : ""}"><span class="e">💼</span><b>Вакансия</b><small>Ищу человека на роль или задачу</small></button>
        </div>`}
      <div class="card rise" style="--i:2;margin-top:12px">
        <div data-only="vacancy">
          <label style="margin-top:0">Стартап</label>
          <select name="startup_id">
            <option value="">Без привязки к стартапу</option>
            ${startups.map((s) => `<option value="${s.id}" ${p.startup?.id === s.id ? "selected" : ""}>${esc(s.title)}</option>`).join("")}
          </select>
          <div class="hint">Вакансия появится на странице вашего стартапа.</div>
        </div>
        <label id="titleLabel">Название <span class="req">*</span></label>
        <input name="title" maxlength="140" value="${esc(p.title)}" placeholder="Например: Learnly — микрообучение для команд" />
        <label>Кратко <span class="req">*</span></label>
        <textarea name="summary" maxlength="280" style="min-height:70px" placeholder="Одно-два предложения — их увидят в ленте">${esc(p.summary)}</textarea>
        <div class="hint"><span id="sumCount">0</span>/280</div>
      </div>
      <div class="card rise" style="--i:3">
        <label style="margin-top:0">Подробное описание</label>
        <textarea name="description" maxlength="8000" placeholder="Что за продукт, какие результаты, чем живёт команда">${esc(p.description)}</textarea>
        <label id="lfLabel">Кого ищем</label>
        <textarea name="looking_for" maxlength="4000">${esc(p.looking_for)}</textarea>
        <label>Навыки / теги</label>
        <input name="skills" value="${esc((p.skills || []).join(", "))}" placeholder="Python, B2B, Маркетинг" />
        <div class="hint">Через запятую — по ним публикацию найдут в поиске.</div>
      </div>
      <div class="card rise" style="--i:4">
        <div class="row" style="gap:12px;align-items:flex-start">
          <div class="grow" style="min-width:140px" data-only="startup"><label style="margin-top:0">Стадия</label><select name="stage">${opt(STAGE, p.stage, "Не указана")}</select></div>
          <div class="grow" style="min-width:140px"><label style="margin-top:0">Формат</label><select name="work_format">${opt(FORMAT, p.work_format, "Не указан")}</select></div>
        </div>
        <label>Условия / компенсация</label>
        <input name="compensation" maxlength="120" value="${esc(p.compensation)}" placeholder="Например: 150–200 тыс. ₽ или доля 5%" />
      </div>
      <div class="err" id="ferr"></div>
      <div class="cta-bar"><button class="btn block lg" id="submitBtn">${post ? "Сохранить изменения" : "✨ Опубликовать"}</button></div>
    </form>`;

  const form = document.getElementById("postForm");
  let kind = p.kind;
  const syncKind = () => {
    form.querySelectorAll("[data-only]").forEach((x) => (x.hidden = x.dataset.only !== kind));
    document.getElementById("lfLabel").textContent = kind === "startup" ? "Кого ищем — команда, инвестиции, партнёры" : "Требования к кандидату";
  };
  syncKind();
  const kindEl = document.getElementById("kind");
  if (kindEl) kindEl.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    tap();
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
    const fail = (msg) => { err.textContent = msg; haptic("error"); err.scrollIntoView({ behavior: "smooth", block: "center" }); };
    if (f.title.trim().length < 3) return fail("Название — минимум 3 символа");
    if (f.summary.trim().length < 10) return fail("Краткое описание — минимум 10 символов");
    const body = {
      title: f.title, summary: f.summary, description: f.description, looking_for: f.looking_for,
      skills: f.skills.split(",").map((s) => s.trim()).filter(Boolean),
      work_format: f.work_format || null, compensation: f.compensation,
    };
    if (kind === "startup") body.stage = f.stage || null;
    if (kind === "vacancy") body.startup_id = f.startup_id ? +f.startup_id : null;
    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    try {
      const saved = post
        ? await api(`/api/posts/${post.id}`, { method: "PATCH", body })
        : await api("/api/posts", { method: "POST", body: { ...body, kind } });
      haptic("success");
      toast(post ? "Изменения сохранены" : "Опубликовано! Теперь её видят участники клуба");
      location.hash = `#/post/${saved.id}`;
    } catch (e) {
      fail(e.message);
      btn.disabled = false;
    }
  };
}

router();
