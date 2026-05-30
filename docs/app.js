const catTypes = [
  { name: "Fine", weight: 1000 },
  { name: "Nice", weight: 750 },
  { name: "Good", weight: 500 },
  { name: "Rare", weight: 350 },
  { name: "Wild", weight: 275 },
  { name: "Baby", weight: 230 },
  { name: "Epic", weight: 200 },
  { name: "Sus", weight: 175 },
  { name: "Zombie", weight: 160 },
  { name: "Brave", weight: 150 },
  { name: "Rickroll", weight: 125 },
  { name: "Reverse", weight: 100 },
  { name: "Superior", weight: 80 },
  { name: "Trash", weight: 50 },
  { name: "Legendary", weight: 35 },
  { name: "Mythic", weight: 25 },
  { name: "8bit", weight: 20 },
  { name: "Chef", weight: 18 },
  { name: "Jamming", weight: 17 },
  { name: "Corrupt", weight: 15 },
  { name: "Professor", weight: 10 },
  { name: "Water", weight: 8.5 },
  { name: "Fire", weight: 8.5 },
  { name: "Candy", weight: 8 },
  { name: "Divine", weight: 8 },
  { name: "Alien", weight: 6 },
  { name: "Real", weight: 5 },
  { name: "Ultimate", weight: 3 },
  { name: "eGirl", weight: 2 },
  { name: "TV", weight: 1 },
  { name: "Donut", weight: 0.5 },
  { name: "Santa", weight: 0 },
  { name: "Elf", weight: 0 },
  { name: "Snowman", weight: 0 },
  { name: "ChristmasTree", weight: 0 },
  { name: "Gingerbread", weight: 0 },
  { name: "Cocoa", weight: 0 },
  { name: "Present", weight: 0 }
];

let commands = [];
let webSession = {
  sid: "",
  apiBase: "",
  tab: "wiki"
};

function qs(id) {
  return document.getElementById(id);
}

function switchTab(tab) {
  const isWiki = tab === "wiki";
  qs("tab-wiki").classList.toggle("is-active", isWiki);
  qs("tab-inventory").classList.toggle("is-active", !isWiki);
  qs("panel-wiki").classList.toggle("is-active", isWiki);
  qs("panel-inventory").classList.toggle("is-active", !isWiki);
}

function readSessionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const rawUrl = window.location.href;
  const sid = params.get("sid") || params.get("session") || (rawUrl.match(/[?&]sid=([^&#]+)/)?.[1] ? decodeURIComponent(rawUrl.match(/[?&]sid=([^&#]+)/)[1]) : "") || "";
  const apiValue = params.get("api") || params.get("base") || (rawUrl.match(/[?&]api=([^&#]+)/)?.[1] ? decodeURIComponent(rawUrl.match(/[?&]api=([^&#]+)/)[1]) : "") || "";
  const apiBase = apiValue.replace(/\/$/, "");
  const tab = params.get("tab") || window.location.hash.replace(/^#/, "");

  webSession = {
    apiBase,
    sid,
    tab: tab || "wiki"
  };

  return { rawUrl, params, tab };
}

function setConnectionStatus() {
  qs("session-status").textContent = webSession.sid ? "Connected" : "Waiting for signed link";
  qs("session-guild").textContent = webSession.sid ? "Auto-detected" : "-";
  qs("session-user").textContent = webSession.sid ? "Auto-detected" : "-";
  qs("session-api").textContent = webSession.apiBase || "-";
}

function renderDebugInfo(debugState) {
  const node = qs("session-debug");
  if (!node) {
    return;
  }

  node.textContent = [
    `href: ${debugState.rawUrl}`,
    `search: ${window.location.search || "(empty)"}`,
    `hash: ${window.location.hash || "(empty)"}`,
    `sid: ${webSession.sid || "(missing)"}`,
    `apiBase: ${webSession.apiBase || "(missing)"}`,
    `tab: ${webSession.tab || "(missing)"}`,
  ].join("\n");
}

function renderCatsWiki() {
  const holder = qs("wiki-cats");
  holder.innerHTML = "";
  for (const cat of catTypes) {
    const card = document.createElement("article");
    card.className = "cat-card";
    const spawnable = cat.weight > 0 ? "Spawnable" : "Seasonal/disabled";
    card.innerHTML = `<h3 class="cmd-name">${cat.name}</h3><p class="cmd-desc">Weight: ${cat.weight}</p><p class="muted">${spawnable}</p>`;
    holder.appendChild(card);
  }
}

function renderCommandsWiki() {
  const query = qs("wiki-search").value.trim().toLowerCase();
  const holder = qs("wiki-commands");
  holder.innerHTML = "";

  const filtered = commands.filter((c) => {
    const hay = `${c.name} ${c.description || ""}`.toLowerCase();
    return hay.includes(query);
  });

  for (const cmd of filtered) {
    const card = document.createElement("article");
    card.className = "wiki-card";
    card.innerHTML = `
      <h3 class="cmd-name">/${cmd.name}</h3>
      <p class="cmd-desc">${cmd.description || "No description."}</p>
    `;
    holder.appendChild(card);
  }

  if (!filtered.length) {
    holder.innerHTML = `<p class="muted">No commands matched your search.</p>`;
  }
}

function setStatus(text, isError = false) {
  const node = qs("inventory-status");
  node.textContent = text;
  node.style.color = isError ? "#b42318" : "#665f57";
}

function getApiBase() {
  if (!webSession.apiBase) {
    throw new Error("Missing API base URL in the signed link");
  }
  return webSession.apiBase.replace(/\/$/, "");
}

function getAuthHeaders() {
  if (!webSession.sid) {
    throw new Error("Missing inventory session");
  }
  return {
    "X-Inventory-Session": webSession.sid
  };
}

function renderCatsReadonly(cats) {
  const holder = qs("cats-readonly");
  const byType = (cats && cats.by_type) || {};
  const entries = Object.entries(byType).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    holder.textContent = "No cats recorded for this profile yet.";
    return;
  }
  holder.innerHTML = entries.slice(0, 40).map(([name, amount]) => `${name}: ${amount}`).join("<br>");
}

async function loadInventory() {
  try {
    setStatus("Loading inventory...");
    if (!webSession.sid) {
      throw new Error("Open this page from /inventory so it can sign your session automatically.");
    }
    const url = `${getApiBase()}/api/inventory?sid=${encodeURIComponent(webSession.sid)}`;
    const res = await fetch(url, {
      method: "GET",
      headers: getAuthHeaders()
    });
    const body = await res.json();
    if (!res.ok || !body.ok) {
      throw new Error(body.error || "Failed to load inventory");
    }
    const inventory = body.inventory || {};
    qs("inventory-view").classList.remove("hidden");
    qs("inv-kibble").textContent = String(inventory.kibble || 0);
    qs("inv-cat-total").textContent = String(inventory.cats?.total || 0);
    qs("inv-pack-types").textContent = String(Object.keys(inventory.packs || {}).length);
    qs("inv-item-types").textContent = String(Object.keys(inventory.items || {}).length);

    const packs = inventory.packs || {};
    const packEntries = Object.entries(packs).sort((a, b) => a[0].localeCompare(b[0]));
    qs("packs-readonly").innerHTML = packEntries.length
      ? packEntries.map(([name, amount]) => `${name}: ${amount}`).join("<br>")
      : "No packs recorded for this profile yet.";

    const items = inventory.items || {};
    const itemEntries = Object.entries(items).sort((a, b) => a[0].localeCompare(b[0]));
    qs("items-readonly").innerHTML = itemEntries.length
      ? itemEntries.map(([name, amount]) => `${name}: ${amount}`).join("<br>")
      : "No items recorded for this profile yet.";

    renderCatsReadonly(inventory.cats || {});
    setStatus("Inventory loaded.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
}

async function bootWiki() {
  try {
    const res = await fetch("data/commands.json");
    commands = await res.json();
  } catch (_err) {
    commands = [];
  }
  renderCommandsWiki();
  renderCatsWiki();
}

function init() {
  const debugState = readSessionFromUrl();
  setConnectionStatus();
  renderDebugInfo(debugState);

  qs("tab-wiki").addEventListener("click", () => switchTab("wiki"));
  qs("tab-inventory").addEventListener("click", () => switchTab("inventory"));
  qs("wiki-search").addEventListener("input", renderCommandsWiki);
  qs("load-inventory").addEventListener("click", loadInventory);

  bootWiki();
  if (webSession.sid) {
    switchTab("inventory");
  } else if (webSession.tab === "inventory") {
    switchTab("inventory");
  }
  if (webSession.sid && webSession.apiBase) {
    loadInventory();
  } else {
    setStatus("Open this page from /inventory to auto-connect.");
  }
}

init();
