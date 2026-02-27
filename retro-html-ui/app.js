const API_BASE_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "retro_chatrooms_v1";
const FIXED_LEADER_AGENT = "yapper";
const ALWAYS_ACTIVE_AGENT = "auditor";
const DEFAULT_AGENTS = [FIXED_LEADER_AGENT, "definer", "redditor", "engager", ALWAYS_ACTIVE_AGENT];

let currentUser = "";
let currentRoom = "General Chat";
let currentAgents = [...DEFAULT_AGENTS];
let kickableAgents = [];
let activeSupportingAgents = [];

const errorEl = document.getElementById("error");
const loginPageEl = document.getElementById("loginpage");
const chatUiEl = document.getElementById("chat-ui");
const usernameInput = document.getElementById("username");
const welcomeEl = document.getElementById("welcome");
const loginBtn = document.getElementById("loginbutton");
const roomSelect = document.getElementById("room-select");
const newRoomInput = document.getElementById("new-room-name");
const createRoomBtn = document.getElementById("create-room-btn");
const enterRoomBtn = document.getElementById("enter-room-btn");
const deleteRoomBtn = document.getElementById("delete-room-btn");
const currentRoomEl = document.getElementById("currentroom");
const modelInput = document.getElementById("model");
const saveToSelect = document.getElementById("save_to");
const leaderNodeEl = document.getElementById("leader-node");
const activeAgentsListEl = document.getElementById("active-agents-list");
const kickedAgentsListEl = document.getElementById("kicked-agents-list");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("messagevalue");
const chatLog = document.getElementById("chatlog");
const sendBtn = document.getElementById("sendbutton");

function setError(message) {
  if (!message) {
    errorEl.hidden = true;
    errorEl.textContent = "";
    return;
  }

  errorEl.hidden = false;
  errorEl.textContent = message;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);

  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  html = html.replace(/_([^_\n]+)_/g, "<em>$1</em>");

  return html;
}

function renderMarkdownToHtml(markdown) {
  const safeMarkdown = typeof markdown === "string" ? markdown : String(markdown ?? "");
  const normalized = safeMarkdown.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return "<p></p>";
  }

  const codeBlocks = [];
  const withPlaceholders = normalized.replace(
    /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g,
    (_, language, code) => {
      const id = codeBlocks.push({
        language: language || "",
        code: escapeHtml(code.trimEnd()),
      }) - 1;
      return `@@CODE_BLOCK_${id}@@`;
    }
  );

  const blocks = withPlaceholders
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  const htmlBlocks = blocks.map((block) => {
    if (/^@@CODE_BLOCK_\d+@@$/.test(block)) {
      return block;
    }

    const headingMatch = block.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      return `<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`;
    }

    const lines = block.split("\n");

    if (lines.every((line) => /^[-*+]\s+/.test(line))) {
      const items = lines
        .map((line) => line.replace(/^[-*+]\s+/, ""))
        .map((line) => `<li>${renderInlineMarkdown(line)}</li>`)
        .join("");
      return `<ul>${items}</ul>`;
    }

    if (lines.every((line) => /^\d+\.\s+/.test(line))) {
      const items = lines
        .map((line) => line.replace(/^\d+\.\s+/, ""))
        .map((line) => `<li>${renderInlineMarkdown(line)}</li>`)
        .join("");
      return `<ul>${items}</ul>`;
    }

    if (lines.every((line) => /^>\s?/.test(line))) {
      const quote = lines
        .map((line) => line.replace(/^>\s?/, ""))
        .map((line) => renderInlineMarkdown(line))
        .join("<br />");
      return `<blockquote>${quote}</blockquote>`;
    }

    // Heuristic for model output that omits markdown bullets but uses:
    // "Title - description" on separate lines.
    // Supports optional intro line ending with ":" and optional trailing paragraph.
    const nonEmptyLines = lines.map((line) => line.trim()).filter(Boolean);
    const isTitleDesc = (line) => line.includes(" - ") && !/^\d+\.\s+/.test(line);
    const listLineCount = nonEmptyLines.filter(isTitleDesc).length;
    const isNumbered = (line) => /^\d+\.\s+/.test(line);
    const numberedCount = nonEmptyLines.filter(isNumbered).length;

    if (numberedCount >= 2) {
      const parts = [];
      let index = 0;

      if (!isNumbered(nonEmptyLines[0])) {
        parts.push(`<p>${renderInlineMarkdown(nonEmptyLines[0])}</p>`);
        index = 1;
      }

      const listItems = [];
      while (index < nonEmptyLines.length && isNumbered(nonEmptyLines[index])) {
        listItems.push(
          `<li>${renderInlineMarkdown(nonEmptyLines[index].replace(/^\d+\.\s+/, ""))}</li>`
        );
        index += 1;
      }

      if (listItems.length > 0) {
        parts.push(`<ul>${listItems.join("")}</ul>`);
      }

      if (index < nonEmptyLines.length) {
        const tail = nonEmptyLines.slice(index).map((line) => renderInlineMarkdown(line)).join("<br />");
        parts.push(`<p>${tail}</p>`);
      }

      if (parts.length > 0) {
        return parts.join("");
      }
    }

    if (listLineCount >= 2) {
      let start = 0;
      const parts = [];

      if (nonEmptyLines[0].endsWith(":")) {
        parts.push(`<p>${renderInlineMarkdown(nonEmptyLines[0])}</p>`);
        start = 1;
      }

      const listItems = [];
      let index = start;
      while (index < nonEmptyLines.length && isTitleDesc(nonEmptyLines[index])) {
        listItems.push(`<li>${renderInlineMarkdown(nonEmptyLines[index])}</li>`);
        index += 1;
      }

      if (listItems.length > 0) {
        parts.push(`<ul>${listItems.join("")}</ul>`);
      }

      if (index < nonEmptyLines.length) {
        const tail = nonEmptyLines.slice(index).map((line) => renderInlineMarkdown(line)).join("<br />");
        parts.push(`<p>${tail}</p>`);
      }

      if (parts.length > 0) {
        return parts.join("");
      }
    }

    const paragraph = lines.map((line) => renderInlineMarkdown(line)).join("<br />");
    return `<p>${paragraph}</p>`;
  });

  let html = htmlBlocks.join("");
  html = html.replace(/@@CODE_BLOCK_(\d+)@@/g, (_, id) => {
    const block = codeBlocks[Number(id)];
    const className = block.language ? ` class="language-${block.language}"` : "";
    return `<pre><code${className}>${block.code}</code></pre>`;
  });

  return html;
}

function loadStore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { users: {} };

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || typeof parsed.users !== "object") {
      return { users: {} };
    }

    return parsed;
  } catch {
    return { users: {} };
  }
}

function saveStore(store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

function getUserData() {
  const store = loadStore();
  const existing = store.users[currentUser];

  if (existing && existing.rooms && Object.keys(existing.rooms).length > 0) {
    return existing;
  }

  const created = {
    lastRoom: "General Chat",
    rooms: {
      "General Chat": [],
    },
  };

  store.users[currentUser] = created;
  saveStore(store);
  return created;
}

function saveUserData(userData) {
  const store = loadStore();
  store.users[currentUser] = userData;
  saveStore(store);
}

function appendLine(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `line-${role}`;

  const hr = document.createElement("hr");
  const body = document.createElement("div");
  body.className = "message-body";
  body.innerHTML = renderMarkdownToHtml(text);

  wrapper.appendChild(hr);
  wrapper.appendChild(body);
  chatLog.appendChild(wrapper);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderRoomList() {
  const userData = getUserData();
  const roomNames = Object.keys(userData.rooms);

  roomSelect.innerHTML = "";
  roomNames.forEach((room) => {
    const option = document.createElement("option");
    option.value = room;
    option.textContent = room;
    roomSelect.appendChild(option);
  });

  if (roomNames.includes(currentRoom)) {
    roomSelect.value = currentRoom;
  }
}

function renderCurrentRoom() {
  const userData = getUserData();
  const rawHistory = userData.rooms[currentRoom] || [];
  const history = Array.isArray(rawHistory) ? rawHistory : [];

  currentRoomEl.textContent = `Room: ${currentRoom}`;
  chatLog.innerHTML = "";

  history.forEach((line) => {
    if (typeof line === "string") {
      appendLine("system", line);
      return;
    }

    if (!line || typeof line !== "object") {
      return;
    }

    const role = typeof line.role === "string" ? line.role : "system";
    const text = "text" in line ? line.text : "";
    appendLine(role, text);
  });

  if (history.length === 0) {
    appendLine("system", `No previous messages in ${currentRoom}.`);
  }
}

function persistLine(role, text) {
  const userData = getUserData();
  if (!userData.rooms[currentRoom]) {
    userData.rooms[currentRoom] = [];
  }

  userData.rooms[currentRoom].push({ role, text, timestamp: Date.now() });
  userData.lastRoom = currentRoom;
  saveUserData(userData);
}

function enterRoom(name) {
  const roomName = name.trim();
  if (!roomName) return;

  const userData = getUserData();
  if (!userData.rooms[roomName]) {
    setError("Room does not exist for this user.");
    return;
  }

  currentRoom = roomName;
  userData.lastRoom = currentRoom;
  saveUserData(userData);
  setError("");
  renderRoomList();
  renderCurrentRoom();
}

function createRoom() {
  const roomName = newRoomInput.value.trim();
  if (!roomName) return;

  const userData = getUserData();
  if (userData.rooms[roomName]) {
    setError("Room already exists.");
    enterRoom(roomName);
    return;
  }

  userData.rooms[roomName] = [];
  userData.lastRoom = roomName;
  saveUserData(userData);
  newRoomInput.value = "";
  setError("");
  enterRoom(roomName);
}

async function deleteRoom() {
  const roomName = (roomSelect.value || currentRoom || "").trim();
  if (!roomName || !currentUser) return;

  const shouldDelete = window.confirm(`Delete room "${roomName}"? This removes local and backend chat history.`);
  if (!shouldDelete) return;

  const sessionId = `${currentUser}::${roomName}`;
  if (deleteRoomBtn) {
    deleteRoomBtn.disabled = true;
    deleteRoomBtn.textContent = "Deleting...";
  }

  try {
    const res = await fetch(`${API_BASE_URL}/session/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }

    const userData = getUserData();
    delete userData.rooms[roomName];

    const remainingRooms = Object.keys(userData.rooms);
    if (remainingRooms.length === 0) {
      userData.rooms["General Chat"] = [];
    }

    const updatedRooms = Object.keys(userData.rooms);
    if (roomName === currentRoom || !userData.rooms[userData.lastRoom]) {
      currentRoom = updatedRooms[0];
      userData.lastRoom = currentRoom;
    }

    saveUserData(userData);
    setError("");
    renderRoomList();
    renderCurrentRoom();
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to delete room");
  } finally {
    if (deleteRoomBtn) {
      deleteRoomBtn.disabled = false;
      deleteRoomBtn.textContent = "Delete Room";
    }
  }
}

async function fetchAgents() {
  const res = await fetch(`${API_BASE_URL}/agents`);
  if (!res.ok) {
    throw new Error(await res.text());
  }

  const data = await res.json();
  return Array.isArray(data.agents) && data.agents.length ? data.agents : ["yapper"];
}

function initializeAgentParticipation(agents) {
  const uniqueAgents = Array.from(new Set((Array.isArray(agents) ? agents : []).map((agent) => String(agent))));
  currentAgents = uniqueAgents.length ? uniqueAgents : [...DEFAULT_AGENTS];
  kickableAgents = currentAgents.filter(
    (agent) => agent !== FIXED_LEADER_AGENT && agent !== ALWAYS_ACTIVE_AGENT
  );
  activeSupportingAgents = [...kickableAgents];
  renderAgentParticipation();
}

function currentSessionId() {
  return `${currentUser}::${currentRoom}`;
}

function renderAgentParticipation() {
  if (leaderNodeEl) {
    leaderNodeEl.textContent = `Leader: ${FIXED_LEADER_AGENT} (locked)`;
  }

  if (activeAgentsListEl) {
    const fixedItems = `
      <li><span class="agent-name">${FIXED_LEADER_AGENT}</span><span class="agent-muted">leader (locked)</span></li>
      <li><span class="agent-name">${ALWAYS_ACTIVE_AGENT}</span><span class="agent-muted">safety node (locked)</span></li>
    `;
    const supportingItems = activeSupportingAgents
      .map(
        (agent) =>
          `<li><span class="agent-name">${escapeHtml(
            agent
          )}</span><button type="button" class="agent-action" data-action="kick" data-agent="${escapeHtml(
            agent
          )}">Kick</button></li>`
      )
      .join("");
    activeAgentsListEl.innerHTML = `${fixedItems}${supportingItems}`;
  }

  if (kickedAgentsListEl) {
    const kickedAgents = kickableAgents.filter((agent) => !activeSupportingAgents.includes(agent));
    if (!kickedAgents.length) {
      kickedAgentsListEl.innerHTML = `<li><span class="agent-muted">No kicked out agents.</span></li>`;
      return;
    }

    kickedAgentsListEl.innerHTML = kickedAgents
      .map(
        (agent) =>
          `<li><span class="agent-name">${escapeHtml(
            agent
          )}</span><button type="button" class="agent-action" data-action="add" data-agent="${escapeHtml(
            agent
          )}">Add Back</button></li>`
      )
      .join("");
  }
}

function kickAgent(agent) {
  if (!kickableAgents.includes(agent)) return;
  activeSupportingAgents = activeSupportingAgents.filter((name) => name !== agent);
  renderAgentParticipation();
}

function addAgent(agent) {
  if (!kickableAgents.includes(agent)) return;
  if (!activeSupportingAgents.includes(agent)) {
    activeSupportingAgents.push(agent);
    renderAgentParticipation();
  }
}

async function login() {
  const draft = usernameInput.value.trim();
  if (!draft) return;

  currentUser = draft;
  const userData = getUserData();
  currentRoom = userData.lastRoom && userData.rooms[userData.lastRoom] ? userData.lastRoom : "General Chat";

  welcomeEl.textContent = `Welcome ${currentUser}`;
  loginPageEl.hidden = true;
  chatUiEl.hidden = false;
  setError("");

  renderRoomList();
  renderCurrentRoom();

  try {
    currentAgents = await fetchAgents();
    initializeAgentParticipation(currentAgents);
  } catch (err) {
    initializeAgentParticipation(DEFAULT_AGENTS);
    setError(err instanceof Error ? err.message : "Failed to load agents");
  }
}

async function sendMessage(event) {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message || !currentUser) return;

  const userLine = `${currentUser}: ${message}`;
  appendLine("user", userLine);
  persistLine("user", userLine);

  messageInput.value = "";
  setError("");

  const activeAgent = FIXED_LEADER_AGENT;
  const enabledAgents = Array.from(new Set([activeAgent, ...activeSupportingAgents]));
  const payload = {
    message,
    active_agent: activeAgent,
    enabled_agents: enabledAgents,
    model_name: (modelInput && modelInput.value.trim()) || "gpt-4o-mini",
    save_to: saveToSelect.value || undefined,
    session_id: currentSessionId(),
  };

  sendBtn.disabled = true;
  sendBtn.textContent = "sending...";

  try {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(await res.text());
    }

    const data = await res.json();
    if (Array.isArray(data.agent_messages) && data.agent_messages.length > 0) {
      data.agent_messages.forEach((msg) => {
        if (!msg || typeof msg !== "object") return;
        const agent = typeof msg.agent === "string" ? msg.agent : data.active_agent;
        const text = typeof msg.text === "string" ? msg.text : "";
        if (!text.trim()) return;
        const assistantLine = `${agent}: ${text}`;
        appendLine("assistant", assistantLine);
        persistLine("assistant", assistantLine);
      });
    } else {
      const assistantLine = `${data.active_agent}: ${data.response}`;
      appendLine("assistant", assistantLine);
      persistLine("assistant", assistantLine);
    }
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to send message");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "send";
  }
}

loginBtn.addEventListener("click", login);
usernameInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    login();
  }
});
chatForm.addEventListener("submit", sendMessage);
createRoomBtn.addEventListener("click", createRoom);
newRoomInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    createRoom();
  }
});
enterRoomBtn.addEventListener("click", () => enterRoom(roomSelect.value));
if (deleteRoomBtn) {
  deleteRoomBtn.addEventListener("click", deleteRoom);
}

if (activeAgentsListEl) {
  activeAgentsListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.action !== "kick") return;
    const agent = target.dataset.agent || "";
    kickAgent(agent);
  });
}

if (kickedAgentsListEl) {
  kickedAgentsListEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.action !== "add") return;
    const agent = target.dataset.agent || "";
    addAgent(agent);
  });
}
