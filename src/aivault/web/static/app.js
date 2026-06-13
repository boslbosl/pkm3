"use strict";

const state = { group: "project", q: "", selected: null };

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const esc = (s) => (s == null ? "" : String(s));

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

async function loadStats() {
  const s = await getJSON("/api/stats");
  const bySource = Object.entries(s.by_source || {})
    .map(([k, v]) => `${k}:${v}`).join("  ");
  $("#stats").textContent =
    `${s.sessions} sessions · ${s.messages} msgs · ${s.findings} findings   ${bySource}`;
}

async function loadList() {
  const params = new URLSearchParams({ group: state.group });
  if (state.q) params.set("q", state.q);
  const data = await getJSON("/api/sessions?" + params.toString());
  const list = $("#list");
  list.innerHTML = "";
  if (!data.count) {
    list.appendChild(el("p", "empty", "No sessions."));
    return;
  }
  for (const g of data.groups) {
    const title = el("div", "group-title", `${g.label} (${g.sessions.length})`);
    list.appendChild(title);
    for (const s of g.sessions) {
      const item = el("div", "item");
      item.dataset.id = s.id;
      const t = el("div", "t", s.title || "(untitled)");
      const meta = el("div", "m");
      const date = (s.started_at || s.imported_at || "").slice(0, 10);
      meta.innerHTML =
        `<span class="badge">${esc(s.source_tool)}</span> ` +
        `<span class="badge">${esc(s.status)}</span> ` +
        `${esc(s.os_context)} · ${esc(date)} · ${s.message_count} msgs`;
      item.appendChild(t);
      item.appendChild(meta);
      item.onclick = () => selectSession(s.id, item);
      if (s.id === state.selected) item.classList.add("active");
      list.appendChild(item);
    }
  }
}

function row(label, value, isCode) {
  const tr = el("tr");
  tr.appendChild(el("th", null, label));
  const td = el("td");
  if (value == null || value === "") {
    td.appendChild(el("span", "empty", "—"));
  } else if (isCode) {
    td.appendChild(el("code", null, String(value)));
  } else {
    td.textContent = String(value);
  }
  tr.appendChild(td);
  return tr;
}

async function selectSession(id, item) {
  state.selected = id;
  document.querySelectorAll(".item.active").forEach((n) => n.classList.remove("active"));
  if (item) item.classList.add("active");
  const d = await getJSON("/api/session/" + encodeURIComponent(id));
  const root = $("#detail");
  root.innerHTML = "";
  if (d.error) { root.appendChild(el("p", "empty", d.error)); return; }

  root.appendChild(el("h2", null, d.title || "(untitled)"));

  const table = el("table", "meta");
  const meta = [
    ["Session id", d.id, true],
    ["Source", `${d.source_tool} / ${d.source_kind}`, false],
    ["Source session id", d.source_session_id, true],
    ["OS context", d.os_context, false],
    ["Project", d.project_name, false],
    ["Repo / root", d.project_root, true],
    ["Status", d.status, false],
    ["Sensitivity", d.sensitivity, false],
    ["Started", d.started_at, false],
    ["Ended", d.ended_at, false],
    ["Imported", d.imported_at, false],
    ["Messages", d.message_count, false],
    ["Content hash", d.content_hash, true],
    ["Dedupe key", d.dedupe_key, true],
    ["Source fingerprint", d.source_fingerprint, true],
    ["Raw artifact", d.raw_artifact ? d.raw_artifact.stored_path : null, true],
    ["Original path", d.raw_artifact ? d.raw_artifact.original_path : null, true],
  ];
  meta.forEach(([l, v, c]) => table.appendChild(row(l, v, c)));
  root.appendChild(table);

  if (d.tags && d.tags.length) {
    root.appendChild(el("h3", null, "Tags"));
    const wrap = el("div");
    d.tags.forEach((t) => wrap.appendChild(el("span", "chip", t)));
    root.appendChild(wrap);
  }
  if (d.files && d.files.length) {
    root.appendChild(el("h3", null, "Files"));
    d.files.forEach((f) => { const p = el("div"); p.appendChild(el("code", null, f)); root.appendChild(p); });
  }
  if (d.commands && d.commands.length) {
    root.appendChild(el("h3", null, "Commands"));
    d.commands.forEach((c) => { const p = el("div"); p.appendChild(el("code", null, c)); root.appendChild(p); });
  }
  if (d.redaction_findings && d.redaction_findings.length) {
    root.appendChild(el("h3", null, "Redaction findings"));
    d.redaction_findings.forEach((f) =>
      root.appendChild(el("div", "finding", `[${f.confidence}] ${f.kind}: ${f.excerpt}`)));
  }

  root.appendChild(el("h3", null, "Transcript"));
  d.messages.forEach((m) => {
    const box = el("div", "msg");
    box.appendChild(el("div", "role", `${m.role}${m.created_at ? " · " + m.created_at : ""}`));
    const pre = el("pre"); pre.textContent = m.content || ""; box.appendChild(pre);
    root.appendChild(box);
  });
}

function init() {
  document.querySelectorAll(".views button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll(".views button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      state.group = b.dataset.group;
      loadList();
    };
  });
  let timer;
  $("#search").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.q = e.target.value.trim(); loadList(); }, 200);
  });
  loadStats();
  loadList();
}

init();
