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
let loadedInventory = null;

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

function buildApiUrl(path) {
  const base = qs("api-base").value.trim().replace(/\/$/, "");
  if (!base) {
    throw new Error("API Base URL is required");
  }
  return `${base}${path}`;
}

function getAuthHeaders() {
  const key = qs("api-key").value.trim();
  if (!key) {
    throw new Error("API Key is required");
  }
  return {
    "Content-Type": "application/json",
    "X-API-Key": key
  };
}

function inventoryIdentifiers() {
  const guildId = qs("guild-id").value.trim();
  const userId = qs("user-id").value.trim();
  if (!guildId || !userId) {
    throw new Error("Guild ID and User ID are required");
  }
  return { guildId, userId };
}

function renderPacksEditor(packs) {
  const holder = qs("packs-editor");
  holder.innerHTML = "";
  const known = ["wooden", "stone", "bronze", "silver", "gold", "platinum", "diamond", "celestial", "festive"];
  for (const key of known) {
    const row = document.createElement("div");
    row.className = "kv-row";
    row.innerHTML = `
      <input type="text" value="${key}" disabled>
      <input type="number" min="0" step="1" data-pack="${key}" value="${packs[key] || 0}">
    `;
    holder.appendChild(row);
  }
}

function renderItemsEditor(items) {
  const holder = qs("items-editor");
  holder.innerHTML = "";
  const keys = Object.keys(items || {});
  if (!keys.length) {
    addItemRow("", 0);
    return;
  }
  for (const key of keys) {
    addItemRow(key, items[key]);
  }
}

function addItemRow(itemKey = "", amount = 0) {
  const holder = qs("items-editor");
  const row = document.createElement("div");
  row.className = "kv-row";
  row.innerHTML = `
    <input type="text" placeholder="item_key (example: candy_cane_I)" data-item-key value="${itemKey}">
    <input type="number" min="0" step="1" data-item-count value="${amount}">
  `;
  holder.appendChild(row);
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

function populateInventoryEditor(inventory) {
  loadedInventory = inventory;
  qs("inventory-editor").classList.remove("hidden");
  qs("inv-kibble").value = inventory.kibble || 0;
  renderPacksEditor(inventory.packs || {});
  renderItemsEditor(inventory.items || {});
  renderCatsReadonly(inventory.cats || {});
}

async function loadInventory() {
  try {
    setStatus("Loading inventory...");
    const { guildId, userId } = inventoryIdentifiers();
    const url = buildApiUrl(`/api/inventory?guild_id=${encodeURIComponent(guildId)}&user_id=${encodeURIComponent(userId)}`);
    const res = await fetch(url, {
      method: "GET",
      headers: getAuthHeaders()
    });
    const body = await res.json();
    if (!res.ok || !body.ok) {
      throw new Error(body.error || "Failed to load inventory");
    }
    populateInventoryEditor(body.inventory);
    setStatus("Inventory loaded.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
}

function gatherEditorPayload() {
  if (!loadedInventory) {
    throw new Error("Load inventory first");
  }
  const { guildId, userId } = inventoryIdentifiers();
  const packs = {};
  for (const node of document.querySelectorAll("[data-pack]")) {
    packs[node.dataset.pack] = Number.parseInt(node.value || "0", 10) || 0;
  }

  const items = {};
  const rows = qs("items-editor").querySelectorAll(".kv-row");
  for (const row of rows) {
    const keyNode = row.querySelector("[data-item-key]");
    const countNode = row.querySelector("[data-item-count]");
    const key = (keyNode.value || "").trim();
    const count = Number.parseInt(countNode.value || "0", 10) || 0;
    if (key && count > 0) {
      items[key] = count;
    }
  }

  return {
    guild_id: Number.parseInt(guildId, 10),
    user_id: Number.parseInt(userId, 10),
    kibble: Number.parseInt(qs("inv-kibble").value || "0", 10) || 0,
    packs,
    items
  };
}

async function saveInventory() {
  try {
    setStatus("Saving...");
    const payload = gatherEditorPayload();
    const url = buildApiUrl("/api/inventory");
    const res = await fetch(url, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) {
      throw new Error(body.error || "Failed to save inventory");
    }
    populateInventoryEditor(body.inventory);
    setStatus("Saved successfully.");
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
  qs("tab-wiki").addEventListener("click", () => switchTab("wiki"));
  qs("tab-inventory").addEventListener("click", () => switchTab("inventory"));
  qs("wiki-search").addEventListener("input", renderCommandsWiki);
  qs("load-inventory").addEventListener("click", loadInventory);
  qs("save-inventory").addEventListener("click", saveInventory);
  qs("add-item-row").addEventListener("click", () => addItemRow("", 0));
  bootWiki();
}

init();
