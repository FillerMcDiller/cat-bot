const pageEl = document.getElementById('page');
const editBtn = document.getElementById('editBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');
const historyBtn = document.getElementById('historyBtn');
const historyPanel = document.getElementById('historyPanel');
const historyList = document.getElementById('historyList');
const historyCloseBtn = document.getElementById('historyCloseBtn');
const navItems = document.querySelectorAll('.sidebar nav li');
const crumbPage = document.getElementById('crumbPage');
const articleHeading = document.getElementById('articleHeading');
const editToolbar = document.getElementById('editToolbar');
const query = new URLSearchParams(window.location.search);
const wikiEditToken = query.get('edit') || '';
const wikiApiBase = (query.get('api') || '').trim().replace(/\/$/, '');
const wikiSaveUrl = wikiApiBase ? `${wikiApiBase}/api/wiki/` : '/api/wiki/';
const wikiHistoryBaseUrl = wikiApiBase ? `${wikiApiBase}/api/wiki/` : '/api/wiki/';
let currentPage = 'overview';
let originalHtml = '';
let isEditing = false;
let isHistoryOpen = false;

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function setHistoryVisibility(visible) {
  isHistoryOpen = visible;
  historyPanel.hidden = !visible;
}

function formatTimestamp(ts) {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown time';
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function renderHistoryItems(items) {
  if (!Array.isArray(items) || items.length === 0) {
    historyList.innerHTML = '<div class="history-item"><strong>No edits yet</strong><span>This page has no recorded changes.</span></div>';
    return;
  }

  historyList.innerHTML = items.map(item => {
    const editor = escapeHtml(item.editor_display || `User ${item.user_id || 'unknown'}`);
    const stamp = escapeHtml(formatTimestamp(item.timestamp));
    const summary = escapeHtml(item.summary || 'Published changes');
    return `<div class="history-item"><strong>${editor}</strong><span>${stamp}</span><div>${summary}</div></div>`;
  }).join('');
}

async function loadHistory(page) {
  historyList.innerHTML = '<div class="history-item"><strong>Loading...</strong><span>Fetching page history.</span></div>';
  try {
    const historyUrl = `${wikiHistoryBaseUrl}?page=${encodeURIComponent(page)}&limit=40`;
    const res = await fetch(historyUrl);
    if (!res.ok) {
      throw new Error('Failed to load history');
    }
    const payload = await res.json();
    renderHistoryItems(payload.entries || []);
  } catch (error) {
    historyList.innerHTML = '<div class="history-item"><strong>History unavailable</strong><span>Could not fetch wiki history from the server.</span></div>';
  }
}

function setEditingMode(isEditing) {
  editToolbar.hidden = !isEditing;
  saveBtn.style.display = isEditing ? '' : 'none';
  cancelBtn.style.display = isEditing ? '' : 'none';
  undoBtn.style.display = isEditing ? '' : 'none';
  redoBtn.style.display = isEditing ? '' : 'none';
  pageEl.contentEditable = isEditing ? 'true' : 'false';
  pageEl.spellcheck = isEditing;
  pageEl.classList.toggle('editable', isEditing);
  saveBtn.textContent = 'Publish';
  editBtn.textContent = isEditing ? 'Done' : 'Edit';
  editBtn.setAttribute('aria-pressed', isEditing ? 'true' : 'false');
}

function closeEditor(discardChanges = true) {
  if (discardChanges) {
    pageEl.innerHTML = originalHtml;
  }
  isEditing = false;
  pageEl.classList.remove('editable');
  setEditingMode(false);
}

function getSelectionRange() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) {
    return null;
  }
  const range = selection.getRangeAt(0);
  if (!pageEl.contains(range.commonAncestorContainer)) {
    return null;
  }
  return range;
}

function execEditorCommand(command, value = null) {
  pageEl.focus();
  document.execCommand(command, false, value);
}

function insertHtml(html) {
  pageEl.focus();
  const range = getSelectionRange();
  if (range) {
    range.deleteContents();
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    const fragment = document.createDocumentFragment();
    while (wrapper.firstChild) {
      fragment.appendChild(wrapper.firstChild);
    }
    range.insertNode(fragment);
    range.collapse(false);
    const selection = window.getSelection();
    if (selection) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
    return;
  }
  pageEl.insertAdjacentHTML('beforeend', html);
}

function promptAndInsertLink() {
  const url = window.prompt('Link URL', 'https://');
  if (!url) {
    return;
  }
  execEditorCommand('createLink', url);
}

function promptAndInsertColor() {
  const color = window.prompt('Text color', '#c05c2f');
  if (!color) {
    return;
  }
  execEditorCommand('foreColor', color);
}

function promptAndInsertDropdown() {
  const title = window.prompt('Dropdown title', 'More info');
  if (!title) {
    return;
  }
  insertHtml(`<details><summary>${title}</summary><p>Dropdown content</p></details>`);
}

function promptAndInsertCode() {
  insertHtml('<pre><code>code here</code></pre>');
}

function promptAndInsertHeader() {
  execEditorCommand('formatBlock', 'h2');
}

function promptAndInsertSection() {
  const title = window.prompt('Section title', 'New section');
  if (!title) {
    return;
  }
  const intro = window.prompt('Section text', 'Add details here.');
  const sectionTitle = escapeHtml(title.trim() || 'New section');
  const sectionBody = escapeHtml((intro || 'Add details here.').trim() || 'Add details here.');
  insertHtml(`<div class="section"><h2>${sectionTitle}</h2><p>${sectionBody}</p></div>`);
}

function ensureEditingContent() {
  if (!pageEl.innerHTML.trim()) {
    pageEl.innerHTML = originalHtml;
  }
}

function formatPageTitle(page) {
  return page.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

async function loadPage(page){
  currentPage = page;
  const title = formatPageTitle(page);
  document.querySelector('.page-title').textContent = title;
  if (crumbPage) {
    crumbPage.textContent = title;
  }
  if (articleHeading) {
    articleHeading.textContent = title;
  }
  // fetch static page if exists
  try{
    const res = await fetch(`./pages/${page}.html`);
    if(res.ok){
      const html = await res.text();
      pageEl.innerHTML = html;
    } else {
      pageEl.innerHTML = `<div class="section"><h2>Overview</h2><div class="codeblock">This page is empty. Press Edit to create content.</div></div>`;
    }
  }catch(e){
    pageEl.innerHTML = `<div class="section"><h2>Error</h2><div class="codeblock">Failed to load page.</div></div>`;
  }
  originalHtml = pageEl.innerHTML;
  pageEl.classList.remove('editable');
  isEditing = false;
  setEditingMode(false);
  if (isHistoryOpen) {
    await loadHistory(currentPage);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navItems.forEach(li=>{
  li.addEventListener('click',()=>{
    navItems.forEach(i=>i.classList.remove('active'));
    li.classList.add('active');
    loadPage(li.dataset.page);
  })
});

editToolbar.addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  if (action === 'section') {
    promptAndInsertSection();
  } else if (action === 'bold') {
    execEditorCommand('bold');
  } else if (action === 'italic') {
    execEditorCommand('italic');
  } else if (action === 'header') {
    promptAndInsertHeader();
  } else if (action === 'link') {
    promptAndInsertLink();
  } else if (action === 'bullet') {
    execEditorCommand('insertUnorderedList');
  } else if (action === 'code') {
    promptAndInsertCode();
  } else if (action === 'dropdown') {
    promptAndInsertDropdown();
  } else if (action === 'color') {
    promptAndInsertColor();
  } else if (action === 'strike') {
    execEditorCommand('strikeThrough');
  } else if (action === 'sub') {
    execEditorCommand('subscript');
  } else if (action === 'hr') {
    execEditorCommand('insertHorizontalRule');
  }
});

editToolbar.addEventListener('mousedown', event => {
  const button = event.target.closest('button[data-action]');
  if (button) {
    event.preventDefault();
  }
});

undoBtn.addEventListener('click', () => {
  if (isEditing) {
    execEditorCommand('undo');
  }
});

redoBtn.addEventListener('click', () => {
  if (isEditing) {
    execEditorCommand('redo');
  }
});

historyBtn.addEventListener('click', async () => {
  const nextVisible = !isHistoryOpen;
  setHistoryVisibility(nextVisible);
  if (nextVisible) {
    await loadHistory(currentPage);
  }
});

historyCloseBtn.addEventListener('click', () => {
  setHistoryVisibility(false);
});

pageEl.addEventListener('input', () => {
  if (isEditing) {
    pageEl.classList.add('editable');
  }
});

editBtn.addEventListener('click',async()=>{
  if (isEditing) {
    closeEditor(true);
    return;
  }

  if (!wikiEditToken) {
    alert('You need the Discord role edit link to save changes.');
    return;
  }
  ensureEditingContent();
  isEditing = true;
  setEditingMode(true);
  pageEl.focus();
});

cancelBtn.addEventListener('click',()=>{
  closeEditor(true);
});

saveBtn.addEventListener('click',async()=>{
  const body = pageEl.innerHTML;
  try{
    const res = await fetch(wikiSaveUrl,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({page: currentPage, html: body, edit_token: wikiEditToken})
    });
    if(res.ok){
      originalHtml = body;
      pageEl.innerHTML = body;
      pageEl.classList.remove('editable');
      isEditing = false;
      setEditingMode(false);
      if (isHistoryOpen) {
        await loadHistory(currentPage);
      }
      alert('Saved');
    } else {
      let payload = null;
      try {
        payload = await res.json();
      } catch (error) {
        payload = null;
      }
      if (res.status === 401) {
        alert('Edit session expired or already used. Run /wiki again to get a fresh edit link.');
      } else if (res.status === 404) {
        alert('Wiki API endpoint was not found. Use the /wiki edit link that includes API parameters.');
      } else {
        const reason = payload && payload.error ? ` (${payload.error})` : '';
        alert(`Save failed${reason}`);
      }
    }
  }catch(e){
    alert('Save failed: '+e.message);
  }
});

// init
navItems[0].classList.add('active');
if (!wikiEditToken) {
  editBtn.disabled = true;
  editBtn.title = 'Open the wiki from the Discord role edit link to make changes';
}
loadPage(currentPage);
