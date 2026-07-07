const pageEl = document.getElementById('page');
const editBtn = document.getElementById('editBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');
const navItems = document.querySelectorAll('.sidebar nav li');
const crumbPage = document.getElementById('crumbPage');
const articleHeading = document.getElementById('articleHeading');
const editToolbar = document.getElementById('editToolbar');
const wikiEditToken = new URLSearchParams(window.location.search).get('edit') || '';
let currentPage = 'overview';
let originalHtml = '';
let isEditing = false;

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
  if (action === 'bold') {
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
    const res = await fetch('/api/wiki/save',{
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
      alert('Saved');
    } else {
      alert('Save failed');
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
