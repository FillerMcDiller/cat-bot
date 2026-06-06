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
let currentInventory = null;
let selectedCatId = "";
let currentWikiTab = "commands";

function qs(id) {
  return document.getElementById(id);
}

function switchTab(tab) {
  const isWiki = tab === "wiki";
  const tabWiki = qs("tab-wiki");
  const tabInventory = qs("tab-inventory");
  const panelWiki = qs("panel-wiki");
  const panelInventory = qs("panel-inventory");
  if (tabWiki) tabWiki.classList.toggle("is-active", isWiki);
  if (tabInventory) tabInventory.classList.toggle("is-active", !isWiki);
  if (panelWiki) panelWiki.classList.toggle("is-active", isWiki);
  if (panelInventory) panelInventory.classList.toggle("is-active", !isWiki);
}

function switchWikiTab(tab) {
  currentWikiTab = tab;
  const tabs = ["commands", "cats", "features"];
  for (const key of tabs) {
    const button = qs(`wiki-tab-${key}`);
    const section = qs(`wiki-section-${key}`);
    if (button) button.classList.toggle("is-active", key === tab);
    if (section) section.classList.toggle("is-active", key === tab);
  }
}

function readSessionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const rawUrl = window.location.href;
  const sid = params.get("sid") || params.get("session") || (rawUrl.match(/[?&]sid=([^&#]+)/)?.[1] ? decodeURIComponent(rawUrl.match(/[?&]sid=([^&#]+)/)[1]) : "") || "";
  const apiValue = params.get("api") || params.get("base") || (rawUrl.match(/[?&]api=([^&#]+)/)?.[1] ? decodeURIComponent(rawUrl.match(/[?&]api=([^&#]+)/)[1]) : "") || "";
  const apiBackupsValue = params.get("api_backups") || params.get("backups") || (rawUrl.match(/[?&]api_backups=([^&#]+)/)?.[1] ? decodeURIComponent(rawUrl.match(/[?&]api_backups=([^&#]+)/)[1]) : "") || "";
  const apiBase = apiValue.replace(/\/$/, "");
  const tab = params.get("tab") || window.location.hash.replace(/^#/, "");

  webSession = {
    apiBase,
    apiBackups: apiBackupsValue ? apiBackupsValue.split(',').map(s=>s.trim()).filter(Boolean).map(s=>s.replace(/\/$/, '')) : [],
    sid,
    tab: tab || "wiki"
  };

  return { rawUrl, params, tab };
}

function setConnectionStatus() {
  const status = qs("session-status");
  const guild = qs("session-guild");
  const user = qs("session-user");
  const api = qs("session-api");
  if (status) status.textContent = webSession.sid ? "Connected" : "Waiting for signed link";
  if (guild) guild.textContent = webSession.sid ? "Auto-detected" : "-";
  if (user) user.textContent = webSession.sid ? "Auto-detected" : "-";
  if (api) api.textContent = webSession.apiBase || "-";
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

function showElement(id, shouldShow) {
  const node = qs(id);
  if (node) {
    node.classList.toggle("hidden", !shouldShow);
  }
}

function textOf(value) {
  return value === undefined || value === null || value === "" ? "-" : String(value);
}

function renderCatsWiki() {
  const holder = qs("wiki-cats");
  if (!holder) {
    return;
  }
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
  const holder = qs("wiki-commands");
  const search = qs("wiki-search");
  if (!holder || !search) {
    return;
  }

  const query = search.value.trim().toLowerCase();
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

async function tryFetchWithBackups(path, options) {
  const candidates = [];
  try {
    candidates.push(getApiBase());
  } catch (e) {}
  if (webSession.apiBackups && webSession.apiBackups.length) {
    for (const b of webSession.apiBackups) {
      if (b && !candidates.includes(b)) candidates.push(b);
    }
  }
  if (!candidates.length) throw new Error('No API base available');

  let lastErr = null;
  for (const base of candidates) {
    const url = base + path;
    try {
      const resp = await fetch(url, options);
      if (resp.ok) return resp;
      lastErr = new Error(`HTTP ${resp.status}`);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

function getAuthHeaders() {
  if (!webSession.sid) {
    throw new Error("Missing inventory session");
  }
  return {
    "X-Inventory-Session": webSession.sid
  };
}

function normalizeCatName(cat) {
  return (cat?.name || cat?.type || "Unnamed").trim();
}

function getFilteredCats() {
  const cats = currentInventory?.cats?.list || [];
  const query = (qs("cat-search")?.value || "").trim().toLowerCase();
  if (!query) {
    return cats;
  }
  return cats.filter((cat) => {
    const hay = `${cat?.name || ""} ${cat?.type || ""} ${cat?.id || ""}`.toLowerCase();
    return hay.includes(query);
  });
}

function renderCatDetails(cat) {
  const card = qs("cat-detail-card");
  if (!card) {
    return;
  }
  if (!cat) {
    card.classList.add("hidden");
    return;
  }

  card.classList.remove("hidden");
  if (qs("cat-detail-title")) qs("cat-detail-title").textContent = `${normalizeCatName(cat)} — ${cat.type || "Unknown"}`;
  if (qs("cat-detail-meta")) qs("cat-detail-meta").textContent = `ID ${cat.id || "?"}`;
  if (qs("cat-detail-name")) qs("cat-detail-name").textContent = normalizeCatName(cat);
  if (qs("cat-detail-bond")) qs("cat-detail-bond").textContent = String(cat.bond || 0);
  if (qs("cat-detail-favorite")) qs("cat-detail-favorite").textContent = cat.favorite ? "Yes" : "No";
  if (qs("cat-detail-adventure")) qs("cat-detail-adventure").textContent = cat.on_adventure ? "Yes" : "No";
  if (qs("cat-rename-input")) qs("cat-rename-input").value = normalizeCatName(cat);

  const itemSelect = qs("cat-item-select");
  if (itemSelect) {
    const items = currentInventory?.items || {};
    const supported = Object.entries(items)
      .filter(([key, amount]) => amount > 0 && /^(ball|dogtreat|pancakes|candy_cane|gingerbread|hot_cocoa|present|ornament|festive_toy|snowglobe)_[A-Z0-9]+$/i.test(key))
      .sort((a, b) => a[0].localeCompare(b[0]));
    itemSelect.innerHTML = supported.length
      ? supported.map(([key, amount]) => `<option value="${key}">${key} x${amount}</option>`).join("")
      : `<option value="">No supported items</option>`;
    itemSelect.disabled = !supported.length;
  }
}

function renderCatsPanel() {
  const holder = qs("cats-grid");
  const detailCard = qs("cat-detail-card");
  if (!holder) {
    return;
  }
  const cats = getFilteredCats();
  holder.innerHTML = "";
  if (!cats.length) {
    holder.innerHTML = `<p class="muted">No cats matched your search.</p>`;
    renderCatDetails(null);
    return;
  }

  let selectedCard = null;
  for (const cat of cats) {
    const card = document.createElement("article");
    card.className = "cat-card inventory-cat";
    const selected = cat.id === selectedCatId;
    if (selected) {
      card.classList.add("selected");
      selectedCard = card;
    }
    card.innerHTML = `
      <h3 class="cmd-name">${normalizeCatName(cat)}</h3>
      <p class="cmd-desc">${cat.type || "Unknown"}</p>
      <p class="muted">Bond ${textOf(cat.bond)}${cat.favorite ? " · Favorite" : ""}${cat.on_adventure ? " · Adventuring" : ""}</p>
    `;
    card.addEventListener("click", () => {
      selectedCatId = cat.id || "";
      renderCatsPanel();
      renderCatDetails(cat);
    });
    holder.appendChild(card);
  }

  const selected = cats.find((cat) => cat.id === selectedCatId) || cats[0];
  if (selected && selectedCatId !== selected.id) {
    selectedCatId = selected.id || "";
    renderCatsPanel();
    renderCatDetails(selected);
    return;
  }

  if (detailCard) {
    detailCard.classList.toggle("hidden", !selected);
    if (selected) {
      holder.appendChild(detailCard);
      if (selectedCard && selectedCard.nextSibling !== detailCard) {
        holder.insertBefore(detailCard, selectedCard.nextSibling);
      }
    }
  }

  renderCatDetails(selected);
}

function renderInventorySummary(inventory) {
  if (qs("inv-kibble")) qs("inv-kibble").textContent = textOf(inventory.kibble || 0);
  if (qs("inv-cat-total")) qs("inv-cat-total").textContent = textOf(inventory.cats?.total || 0);
  if (qs("inv-pack-types")) qs("inv-pack-types").textContent = textOf(Object.keys(inventory.packs || {}).length);
  if (qs("inv-item-types")) qs("inv-item-types").textContent = textOf(Object.keys(inventory.items || {}).length);

  const packs = inventory.packs || {};
  const packEntries = Object.entries(packs).sort((a, b) => a[0].localeCompare(b[0]));
  const packNode = qs("packs-readonly");
  if (packNode) {
    packNode.innerHTML = packEntries.length ? packEntries.map(([name, amount]) => `${name}: ${amount}`).join("<br>") : "No packs recorded for this profile yet.";
  }

  const items = inventory.items || {};
  const itemEntries = Object.entries(items).sort((a, b) => a[0].localeCompare(b[0]));
  const itemNode = qs("items-readonly");
  if (itemNode) {
    itemNode.innerHTML = itemEntries.length ? itemEntries.map(([name, amount]) => `${name}: ${amount}`).join("<br>") : "No items recorded for this profile yet.";
  }
}

async function loadInventory() {
  try {
    setStatus("Loading inventory...");
    if (!webSession.sid) {
      throw new Error("Open this page from /inventory so it can sign your session automatically.");
    }
    const path = `/api/inventory?sid=${encodeURIComponent(webSession.sid)}`;
    const res = await tryFetchWithBackups(path, {
      method: "GET",
      headers: getAuthHeaders()
    });
    const body = await res.json();
    if (!res.ok || !body.ok) {
      throw new Error(body.error || "Failed to load inventory");
    }
    currentInventory = body.inventory || {};
    showElement("inventory-view", true);
    renderInventorySummary(currentInventory);
    renderCatsPanel();
    setStatus("Inventory loaded.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
}

async function performInventoryAction(action, extra = {}) {
  if (!webSession.sid) {
    throw new Error("Missing inventory session");
  }
  if (!selectedCatId) {
    throw new Error("Select a cat first");
  }

  const path = `/api/inventory/action`;
  const res = await tryFetchWithBackups(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders()
    },
    body: JSON.stringify({ action, cat_id: selectedCatId, ...extra })
  });
  const body = await res.json();
  if (!res.ok || !body.ok) {
    throw new Error(body.error || "Inventory action failed");
  }
  currentInventory = body.inventory || currentInventory;
  renderInventorySummary(currentInventory);
  renderCatsPanel();
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

  qs("tab-wiki")?.addEventListener("click", () => switchTab("wiki"));
  qs("tab-inventory")?.addEventListener("click", () => switchTab("inventory"));
  qs("wiki-tab-commands")?.addEventListener("click", () => switchWikiTab("commands"));
  qs("wiki-tab-cats")?.addEventListener("click", () => switchWikiTab("cats"));
  qs("wiki-tab-features")?.addEventListener("click", () => switchWikiTab("features"));
  qs("wiki-search")?.addEventListener("input", renderCommandsWiki);
  qs("cat-search")?.addEventListener("input", renderCatsPanel);
  qs("load-inventory")?.addEventListener("click", loadInventory);
  qs("cat-rename-button")?.addEventListener("click", async () => {
    try {
      const nextName = (qs("cat-rename-input")?.value || "").trim();
      if (!nextName) {
        throw new Error("Enter a new name first");
      }
      await performInventoryAction("rename", { new_name: nextName });
      setStatus("Cat renamed.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  });
  qs("cat-favorite-button")?.addEventListener("click", async () => {
    try {
      await performInventoryAction("favorite");
      setStatus("Favorite updated.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  });
  qs("cat-play-button")?.addEventListener("click", async () => {
    try {
      await performInventoryAction("play");
      setStatus("Played with cat.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  });
  qs("cat-item-button")?.addEventListener("click", async () => {
    try {
      const itemKey = qs("cat-item-select")?.value || "";
      if (!itemKey) {
        throw new Error("No supported item selected");
      }
      const match = itemKey.match(/^(.+)_([A-Z0-9]+)$/i);
      if (!match) {
        throw new Error("Invalid item selection");
      }
      await performInventoryAction("use_item", { item_key: match[1], tier: match[2] });
      setStatus("Item used.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  });

  bootWiki();
  switchWikiTab("commands");
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
