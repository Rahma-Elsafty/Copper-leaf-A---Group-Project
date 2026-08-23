// Copperleaf Ops Console — vanilla JS, no build step, talks to the Flask
// backend (platform/backend.py) which itself talks to the real
// state_graph engine/store, mcp_server.tool_defs, and the RAG documents
// table. Nothing here is mocked; every button here is a real API call.

const API = "/api";

// Known node sequences per graph, for the "pipeline" visualization only.
// This is a DISPLAY convenience (so a run's position is visible at a
// glance) — the real source of truth for state and transitions is always
// the backend's /api/runs/<id> response, never this list. Cycles (e.g.
// food_safety_incident's investigate -> hitl_review -> ... -> investigate)
// are drawn as a straight track with the current node simply highlighted
// wherever it currently is; investigation_cycles (visible in the run's
// state panel) is what actually reveals a revisit.
const NODE_SEQUENCES = {
  supplier_onboarding: ["compliance_check", "hitl_approval", "apply_onboarding_decision", "confirm_agreement", "mark_verified"],
  food_safety_incident: ["investigate", "hitl_review", "apply_review_decision", "verify_corrective_action", "close"],
  purchase_order_fulfillment: ["pending_approval", "apply_approval_decision", "decompose_and_send", "receive_delivery", "reconcile"],
};

const STARTER_FIELDS = {
  supplier_onboarding: [
    { key: "supplier_id", type: "number", label: "Supplier ID", placeholder: "2" },
  ],
  food_safety_incident: [
    { key: "incident_id", type: "number", label: "Incident ID", placeholder: "1" },
    { key: "incident_type", type: "text", label: "Incident type", placeholder: "temperature_breach" },
  ],
  purchase_order_fulfillment: [
    { key: "po_id", type: "number", label: "PO ID", placeholder: "100" },
    { key: "ingredient_id", type: "number", label: "Ingredient ID", placeholder: "1" },
    { key: "supplier_id", type: "number", label: "Supplier ID", placeholder: "1" },
    { key: "qty", type: "number", label: "Qty", placeholder: "50" },
    { key: "unit_cost", type: "number", label: "Unit cost", placeholder: "3.0" },
    { key: "requested_by", type: "number", label: "Requested by (staff ID)", placeholder: "2" },
    { key: "stock_id", type: "number", label: "Stock ID", placeholder: "1" },
  ],
};

let state = { view: "chat", chatAgent: "memory_rag_agent", chatLog: [] };

function toast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.className = "toast"), 3200);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.error || `Request failed (${res.status})`);
  }
  return body;
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function badge(text) {
  return `<span class="badge ${text}">${text}</span>`;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const d = new Date(iso.replace(" ", "T") + "Z");
  const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

// ---------------------------------------------------------------------
// Nav / router
// ---------------------------------------------------------------------

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    state.view = item.dataset.view;
    state.selectedRunId = null;
    render();
  });
});

async function refreshCounts() {
  try {
    const [hitl, tickets] = await Promise.all([
      api("/hitl?status=pending"),
      api("/tickets?status=open"),
    ]);
    document.getElementById("count-hitl").textContent = hitl.length;
    document.getElementById("count-tickets").textContent = tickets.length;
  } catch (e) { /* backend not up yet */ }
}

async function checkBackend() {
  const elStatus = document.getElementById("backend-status");
  try {
    await api("/health");
    elStatus.textContent = "connected";
  } catch (e) {
    elStatus.textContent = "unreachable";
  }
}

function setActiveNav() {
  document.querySelectorAll(".nav-item").forEach((i) => {
    i.classList.toggle("active", i.dataset.view === state.view);
  });
}

async function render() {
  setActiveNav();
  const main = document.getElementById("main");
  main.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    if (state.view === "chat") return renderChat(main);
    if (state.view === "runs") return renderRuns(main);
    if (state.view === "hitl") return renderHitl(main);
    if (state.view === "tickets") return renderTickets(main);
    if (state.view === "agents") return renderAgents(main);
    if (state.view === "rag") return renderRag(main);
  } catch (e) {
    main.innerHTML = `<div class="panel"><h2>Error</h2><div class="empty">${e.message}</div></div>`;
  }
}

// ---------------------------------------------------------------------
// Chat view — memory/RAG + planning agents (best-effort; see backend.py)
// ---------------------------------------------------------------------

function renderChat(main) {
  main.innerHTML = `
    <h1>Chat with agents</h1>
    <div class="page-sub">Switch between the conversational agents. State-graph agents (supplier onboarding, food safety, purchase orders) are structured workflows, not free chat — start and track them under <b>State-graph runs</b>.</div>
    <div class="panel">
      <div class="row" style="margin-bottom:14px;">
        <select id="chat-agent-select" style="width:240px;">
          <option value="memory_rag_agent">Memory / RAG agent</option>
          <option value="planning_agent">Decomposition / Planning agent</option>
        </select>
      </div>
      <div class="chat-log" id="chat-log"></div>
      <div class="row">
        <input type="text" id="chat-input" placeholder="Ask a question…" style="flex:1;" />
        <button class="primary" id="chat-send">Send</button>
      </div>
    </div>
  `;
  const select = document.getElementById("chat-agent-select");
  select.value = state.chatAgent;
  select.onchange = () => { state.chatAgent = select.value; renderChatLog(); };

  renderChatLog();

  const send = async () => {
    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message) return;
    state.chatLog.push({ role: "user", agent: state.chatAgent, text: message });
    input.value = "";
    renderChatLog();
    try {
      const res = await api("/chat", { method: "POST", body: JSON.stringify({ agent: state.chatAgent, message }) });
      if (res.error) {
        state.chatLog.push({ role: "error", agent: state.chatAgent, text: res.error });
      } else {
        state.chatLog.push({ role: "agent", agent: state.chatAgent, text: res.reply ?? "(no reply)" });
      }
    } catch (e) {
      state.chatLog.push({ role: "error", agent: state.chatAgent, text: e.message });
    }
    renderChatLog();
  };
  document.getElementById("chat-send").onclick = send;
  document.getElementById("chat-input").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
}

function renderChatLog() {
  const log = document.getElementById("chat-log");
  const msgs = state.chatLog.filter((m) => m.agent === state.chatAgent);
  log.innerHTML = msgs.length
    ? msgs.map((m) => `<div class="chat-msg ${m.role === "user" ? "user" : m.role === "error" ? "error" : "agent"}">${escapeHtml(m.text)}</div>`).join("")
    : `<div class="empty">No messages yet with this agent.</div>`;
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------------------------------------------------------------
// Runs view
// ---------------------------------------------------------------------

async function renderRuns(main) {
  if (state.selectedRunId) return renderRunDetail(main, state.selectedRunId);

  const [graphs, runs] = await Promise.all([api("/graphs"), api("/runs")]);

  main.innerHTML = `
    <h1>State-graph runs</h1>
    <div class="page-sub">Start a new request against one of the three state-graph agents, or open an existing run to see where it's paused and push it forward.</div>

    <div class="panel">
      <h2>Start a new request</h2>
      <label>Graph</label>
      <select id="start-graph">
        ${graphs.map((g) => `<option value="${g.graph_name}">${g.graph_name} (${g.agent_name})</option>`).join("")}
      </select>
      <div id="start-fields"></div>
      <div class="row" style="margin-top:14px;">
        <button class="primary" id="start-run-btn">Start run</button>
        <label style="margin:0;"><input type="checkbox" id="demo-mode" /> demo mode (skip real MCP writes)</label>
      </div>
    </div>

    <div class="panel">
      <h2>Runs</h2>
      <div id="runs-table"></div>
    </div>
  `;

  const fieldsBox = document.getElementById("start-fields");
  const graphSelect = document.getElementById("start-graph");
  function renderFields() {
    const fields = STARTER_FIELDS[graphSelect.value] || [];
    fieldsBox.innerHTML = fields.map((f) => `
      <label>${f.label}</label>
      <input type="${f.type}" data-key="${f.key}" placeholder="${f.placeholder || ""}" />
    `).join("");
  }
  graphSelect.onchange = renderFields;
  renderFields();

  document.getElementById("start-run-btn").onclick = async () => {
    const initial_state = {};
    fieldsBox.querySelectorAll("input").forEach((inp) => {
      if (inp.value === "") return;
      initial_state[inp.dataset.key] = inp.type === "number" ? Number(inp.value) : inp.value;
    });
    if (document.getElementById("demo-mode").checked) initial_state._demo_mode = true;
    try {
      const res = await api("/runs", { method: "POST", body: JSON.stringify({ graph_name: graphSelect.value, initial_state }) });
      toast(`Run started: ${res.run_id} (${res.status})`);
      state.selectedRunId = res.run_id;
      render();
    } catch (e) { toast(e.message, true); }
  };

  renderRunsTable(runs);
}

function renderRunsTable(runs) {
  const box = document.getElementById("runs-table");
  if (!runs.length) { box.innerHTML = `<div class="empty">No runs yet — start one above.</div>`; return; }
  box.innerHTML = `
    <table>
      <thead><tr><th>Run</th><th>Graph</th><th>Status</th><th>Node</th><th>Updated</th><th></th></tr></thead>
      <tbody>
        ${runs.map((r) => `
          <tr>
            <td class="run-id">${r.run_id}</td>
            <td class="node">${r.graph_name}</td>
            <td>${badge(r.status)}</td>
            <td class="node">${r.current_node || "—"}</td>
            <td class="ts">${timeAgo(r.updated_at)}</td>
            <td><button class="small" data-open="${r.run_id}">Open</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  box.querySelectorAll("[data-open]").forEach((b) => {
    b.onclick = () => { state.selectedRunId = b.dataset.open; render(); };
  });
}

async function renderRunDetail(main, runId) {
  const run = await api(`/runs/${runId}`);
  const seq = NODE_SEQUENCES[run.graph_name] || [];
  const currentIdx = seq.indexOf(run.current_node);

  const pipelineHtml = seq.length
    ? seq.map((n, i) => {
        let cls = "node-chip";
        if (i < currentIdx) cls += " done";
        if (i === currentIdx) {
          cls += " current";
          if (run.status === "failed") cls += " failed";
          if (run.status === "hitl_paused") cls += " hitl";
        }
        return `<span class="${cls}">${n}</span>` + (i < seq.length - 1 ? `<span class="connector"></span>` : "");
      }).join("")
    : `<span class="node-chip current">${run.current_node}</span>`;

  main.innerHTML = `
    <div class="row" style="justify-content:space-between;">
      <h1 class="run-id">${run.run_id}</h1>
      <button class="small" id="back-btn">← All runs</button>
    </div>
    <div class="page-sub">${run.graph_name} · agent: ${run.agent_name || "—"}</div>

    <div class="panel">
      <h2>Pipeline position</h2>
      <div class="pipeline">${pipelineHtml}</div>
      <div class="row" style="margin-top:8px;">
        <span>Status: ${badge(run.status)}</span>
        <span class="node">checkpoint #${run.checkpoint_seq} @ ${run.completed_node}</span>
      </div>
    </div>

    ${run.status === "waiting" ? `
    <div class="panel">
      <h2>Deliver external event</h2>
      <div class="page-sub" style="margin-bottom:8px;">This run is parked waiting on something outside the model (a delivery, a signed agreement, a re-inspection). Simulate that event to push it forward — this is exactly what a real webhook would call.</div>
      <label>Event JSON</label>
      <textarea id="event-json" placeholder='{"delivery_confirmed": true, "delivered_qty": 50}'></textarea>
      <div class="row" style="margin-top:10px;">
        <button class="primary" id="advance-btn">Send event</button>
        <button id="timeout-btn">Simulate timeout</button>
      </div>
    </div>` : ""}

    <div class="panel">
      <h2>Checkpointed state</h2>
      <div class="json-view">${escapeHtml(JSON.stringify(run.state, null, 2))}</div>
    </div>
  `;

  document.getElementById("back-btn").onclick = () => { state.selectedRunId = null; render(); };

  const advanceBtn = document.getElementById("advance-btn");
  if (advanceBtn) {
    advanceBtn.onclick = async () => {
      let event = {};
      const raw = document.getElementById("event-json").value.trim();
      if (raw) { try { event = JSON.parse(raw); } catch { toast("Event must be valid JSON", true); return; } }
      try {
        await api(`/runs/${runId}/advance`, { method: "POST", body: JSON.stringify({ event }) });
        toast("Event delivered");
        render();
      } catch (e) { toast(e.message, true); }
    };
    document.getElementById("timeout-btn").onclick = async () => {
      try {
        await api(`/runs/${runId}/advance`, { method: "POST", body: JSON.stringify({ event: { timed_out: true } }) });
        toast("Timeout simulated");
        render();
      } catch (e) { toast(e.message, true); }
    };
  }
}

// ---------------------------------------------------------------------
// HITL queue
// ---------------------------------------------------------------------

async function renderHitl(main) {
  const tasks = await api("/hitl?status=pending");
  main.innerHTML = `
    <h1>HITL queue</h1>
    <div class="page-sub">Runs paused for a human decision the agent isn't allowed to make alone. Resolving one here resumes the exact run it paused, with your decision merged in.</div>
    <div class="panel"><div id="hitl-list"></div></div>
  `;
  const box = document.getElementById("hitl-list");
  if (!tasks.length) { box.innerHTML = `<div class="empty">No pending HITL tasks. Start a run under State-graph runs to generate one.</div>`; return; }

  box.innerHTML = tasks.map((t) => `
    <div class="panel" style="background:var(--panel-raised);">
      <div class="row" style="justify-content:space-between;">
        <div><b class="run-id">${t.task_id}</b> <span class="node">run ${t.run_id}</span></div>
        ${badge("pending")}
      </div>
      <div class="page-sub" style="margin:6px 0 10px 0;">${escapeHtml(t.reason)}</div>
      <div class="json-view">${escapeHtml(t.payload_json)}</div>
      <label>Notes</label>
      <textarea data-notes-for="${t.task_id}" placeholder="Reasoning for the decision…"></textarea>
      <div class="row" style="margin-top:10px;">
        <input type="text" data-by-for="${t.task_id}" placeholder="Your name" style="width:180px;" />
        <button class="primary" data-approve="${t.task_id}">Approve</button>
        <button class="danger" data-reject="${t.task_id}">Reject</button>
      </div>
    </div>
  `).join("");

  const resolve = async (taskId, approved) => {
    const notes = box.querySelector(`[data-notes-for="${taskId}"]`).value;
    const resolvedBy = box.querySelector(`[data-by-for="${taskId}"]`).value || "unknown_admin";
    try {
      await api(`/hitl/${taskId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ status: approved ? "approved" : "rejected", decision: { approved, notes }, resolved_by: resolvedBy }),
      });
      toast(`HITL task ${approved ? "approved" : "rejected"} — run resumed`);
      render();
      refreshCounts();
    } catch (e) { toast(e.message, true); }
  };
  box.querySelectorAll("[data-approve]").forEach((b) => (b.onclick = () => resolve(b.dataset.approve, true)));
  box.querySelectorAll("[data-reject]").forEach((b) => (b.onclick = () => resolve(b.dataset.reject, false)));
}

// ---------------------------------------------------------------------
// Failure tickets
// ---------------------------------------------------------------------

async function renderTickets(main) {
  const tickets = await api("/tickets?status=open");
  main.innerHTML = `
    <h1>Failure tickets</h1>
    <div class="page-sub">Unplanned failures a retry couldn't fix — a bad tool call, a malformed external event. Distinct from the HITL queue: nothing here was an expected pause.</div>
    <div class="panel"><div id="tickets-list"></div></div>
  `;
  const box = document.getElementById("tickets-list");
  if (!tickets.length) { box.innerHTML = `<div class="empty">No open tickets. Trigger a real failure (e.g. a bad delivery quantity) from a run to see one land here.</div>`; return; }

  box.innerHTML = tickets.map((t) => `
    <div class="panel" style="background:var(--panel-raised);">
      <div class="row" style="justify-content:space-between;">
        <div><b class="run-id">${t.ticket_id}</b> <span class="node">run ${t.run_id} · node ${t.node}</span></div>
        ${badge("open")}
      </div>
      <div class="page-sub" style="margin:6px 0 10px 0;">${escapeHtml(t.error_message)}</div>
      <label>Resolution notes</label>
      <textarea data-notes-for="${t.ticket_id}" placeholder="What was wrong, what you fixed…"></textarea>
      <div class="row" style="margin-top:8px;">
        <label style="margin:0;"><input type="checkbox" data-retry-for="${t.ticket_id}" /> retry from checkpoint after resolving</label>
      </div>
      <label>Retry event JSON (optional — corrected data)</label>
      <textarea data-event-for="${t.ticket_id}" placeholder='{"delivered_qty": 50}'></textarea>
      <div class="row" style="margin-top:10px;">
        <button class="primary" data-resolve="${t.ticket_id}">Resolve</button>
      </div>
    </div>
  `).join("");

  box.querySelectorAll("[data-resolve]").forEach((b) => {
    b.onclick = async () => {
      const id = b.dataset.resolve;
      const notes = box.querySelector(`[data-notes-for="${id}"]`).value;
      const retry = box.querySelector(`[data-retry-for="${id}"]`).checked;
      let event = {};
      const raw = box.querySelector(`[data-event-for="${id}"]`).value.trim();
      if (raw) { try { event = JSON.parse(raw); } catch { toast("Event must be valid JSON", true); return; } }
      try {
        await api(`/tickets/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolution_notes: notes, retry, event }) });
        toast(retry ? "Ticket resolved and run retried from checkpoint" : "Ticket resolved");
        render();
        refreshCounts();
      } catch (e) { toast(e.message, true); }
    };
  });
}

// ---------------------------------------------------------------------
// Agents & tools
// ---------------------------------------------------------------------

async function renderAgents(main) {
  const agents = await api("/agents");
  main.innerHTML = `
    <h1>Agents &amp; tools</h1>
    <div class="page-sub">Toggle which MCP tools each agent may call. This reaches the live MCP server directly (mcp_server/server.py reads this same permission table on every request) — no redeploy needed.</div>
    <div class="panel">
      <label>Agent</label>
      <select id="agent-select">
        ${agents.map((a) => `<option value="${a.agent_name}">${a.agent_name}</option>`).join("")}
      </select>
      <div id="tools-list" style="margin-top:14px;"></div>
    </div>
  `;
  const select = document.getElementById("agent-select");
  const loadTools = async () => {
    const tools = await api(`/agents/${select.value}/tools`);
    const box = document.getElementById("tools-list");
    box.innerHTML = tools.map((t) => `
      <div class="row" style="justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--border);">
        <div>
          <div class="node">${t.name}</div>
          <div class="page-sub" style="margin:2px 0 0 0;">${t.description}</div>
        </div>
        <div class="toggle ${t.allowed ? "on" : ""}" data-tool="${t.name}"><div class="dot"></div></div>
      </div>
    `).join("");
    box.querySelectorAll("[data-tool]").forEach((toggle) => {
      toggle.onclick = async () => {
        const nowOn = !toggle.classList.contains("on");
        try {
          await api(`/agents/${select.value}/tools/${toggle.dataset.tool}`, { method: "POST", body: JSON.stringify({ allowed: nowOn }) });
          toggle.classList.toggle("on", nowOn);
          toast(`${toggle.dataset.tool} ${nowOn ? "enabled" : "disabled"} for ${select.value}`);
        } catch (e) { toast(e.message, true); }
      };
    });
  };
  select.onchange = loadTools;
  loadTools();
}

// ---------------------------------------------------------------------
// RAG documents
// ---------------------------------------------------------------------

async function renderRag(main) {
  const docs = await api("/rag/documents");
  main.innerHTML = `
    <h1>RAG documents</h1>
    <div class="page-sub">Documents added here are read by <code>state_graph.techniques.retrieve_grounding</code> on the very next query (e.g. the food-safety graph's <code>investigate</code> node) — not just stored and ignored.</div>

    <div class="panel">
      <h2>Add a document</h2>
      <label>Title</label>
      <input type="text" id="doc-title" placeholder="Allergen handling — shellfish" />
      <label>Text</label>
      <textarea id="doc-text" placeholder="Full policy text…"></textarea>
      <div class="row" style="margin-top:10px;">
        <button class="primary" id="add-doc-btn">Add document</button>
      </div>
    </div>

    <div class="panel">
      <h2>Documents (${docs.length})</h2>
      <div id="rag-list"></div>
    </div>
  `;

  document.getElementById("add-doc-btn").onclick = async () => {
    const title = document.getElementById("doc-title").value.trim();
    const text = document.getElementById("doc-text").value.trim();
    if (!title || !text) { toast("Title and text are both required", true); return; }
    try {
      await api("/rag/documents", { method: "POST", body: JSON.stringify({ title, text, added_by: "admin" }) });
      toast("Document added");
      render();
    } catch (e) { toast(e.message, true); }
  };

  const box = document.getElementById("rag-list");
  box.innerHTML = docs.length ? docs.map((d) => `
    <div class="row" style="justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--border);">
      <div style="max-width:80%;">
        <div><b>${escapeHtml(d.title)}</b></div>
        <div class="page-sub" style="margin:2px 0 0 0;">${escapeHtml(d.text.slice(0, 140))}${d.text.length > 140 ? "…" : ""}</div>
      </div>
      <button class="danger small" data-remove="${d.doc_id}">Remove</button>
    </div>
  `).join("") : `<div class="empty">No documents yet.</div>`;

  box.querySelectorAll("[data-remove]").forEach((b) => {
    b.onclick = async () => {
      try { await api(`/rag/documents/${b.dataset.remove}`, { method: "DELETE" }); toast("Document removed"); render(); }
      catch (e) { toast(e.message, true); }
    };
  });
}

// ---------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------

checkBackend();
refreshCounts();
setInterval(refreshCounts, 8000);
render();
