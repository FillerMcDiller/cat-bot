const pageEl = document.getElementById('page');
const editBtn = document.getElementById('editBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const navItems = document.querySelectorAll('.sidebar nav li');
const crumbPage = document.getElementById('crumbPage');
const articleHeading = document.getElementById('articleHeading');
const editorPanel = document.getElementById('editorPanel');
const editorToolbar = document.getElementById('editorToolbar');
const sourceEditor = document.getElementById('wikiSource');
const previewPage = document.getElementById('previewPage');
const wikiEditToken = new URLSearchParams(window.location.search).get('edit') || '';
let currentPage = 'overview';
let originalHtml = '';
let originalSource = '';
let currentSource = '';
let isEditing = false;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function sanitizeUrl(value) {
  const url = String(value || '').trim();
  if (!url) {
    return '';
  }
  if (/^(https?:|mailto:|\/|#)/i.test(url)) {
    return url;
  }
  return '';
}

function renderInline(text) {
  const placeholders = [];
  let rendered = escapeHtml(String(text || ''));

  rendered = rendered.replace(/`([^`]+)`/g, (_, code) => {
    const token = `__CODE_${placeholders.length}__`;
    placeholders.push(`<code>${code}</code>`);
    return token;
  });

  rendered = rendered.replace(/\{\{color:([^|}]+)\|([\s\S]+?)\}\}/gi, (_, color, content) => {
    return `<span style="color:${escapeHtml(color.trim())}">${content}</span>`;
  });

  rendered = rendered.replace(/\{\{colour:([^|}]+)\|([\s\S]+?)\}\}/gi, (_, color, content) => {
    return `<span style="color:${escapeHtml(color.trim())}">${content}</span>`;
  });

  rendered = rendered.replace(/\{\{sub\|([\s\S]+?)\}\}/gi, (_, content) => {
    return `<sub>${content}</sub>`;
  });

  rendered = rendered.replace(/\[\[([^|\]]+)\|([\s\S]+?)\]\]/g, (_, url, label) => {
    const safeUrl = sanitizeUrl(url);
    if (!safeUrl) {
      return label;
    }
    return `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer">${label}</a>`;
  });

  rendered = rendered.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
    const safeUrl = sanitizeUrl(url);
    if (!safeUrl) {
      return label;
    }
    return `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer">${label}</a>`;
  });

  rendered = rendered.replace(/'''''([\s\S]+?)'''''/g, '<strong><em>$1</em></strong>');
  rendered = rendered.replace(/'''([\s\S]+?)'''/g, '<strong>$1</strong>');
  rendered = rendered.replace(/''([\s\S]+?)''/g, '<em>$1</em>');
  rendered = rendered.replace(/~~([\s\S]+?)~~/g, '<del>$1</del>');

  placeholders.forEach((replacement, index) => {
    rendered = rendered.replace(`__CODE_${index}__`, replacement);
  });

  return rendered;
}

function renderWiki(source, wrapSections = true) {
  const lines = String(source || '').replace(/\r\n?/g, '\n').split('\n');
  const sections = [];
  let currentSection = [];
  let index = 0;

  function flushSection() {
    const sectionHtml = currentSection.join('');
    if (sectionHtml.trim()) {
      sections.push(sectionHtml);
    }
    currentSection = [];
  }

  function isHeadingLine(line) {
    return /^(=+)\s*(.*?)\s*\1$/.test(line.trim());
  }

  function isBlockStart(line) {
    const trimmed = line.trim();
    return (
      !trimmed ||
      isHeadingLine(trimmed) ||
      /^```/.test(trimmed) ||
      /^\{\{dropdown\s+.+\}\}$/i.test(trimmed) ||
      /^\{\{\/dropdown\}\}$/i.test(trimmed) ||
      /^\{\{end\}\}$/i.test(trimmed) ||
      /^(-{3,}|\*{3,}|_{3,})$/.test(trimmed) ||
      /^([*-])\s+/.test(trimmed) ||
      /^\d+\.\s+/.test(trimmed) ||
      /^>\s?/.test(trimmed)
    );
  }

  function consumeParagraph(startIndex) {
    const paragraphLines = [];
    let cursor = startIndex;
    while (cursor < lines.length) {
      const line = lines[cursor];
      if (!line.trim() || isBlockStart(line)) {
        break;
      }
      paragraphLines.push(line.trimEnd());
      cursor += 1;
    }
    const html = `<p>${paragraphLines.map(line => renderInline(line)).join('<br>')}</p>`;
    return { html, nextIndex: cursor };
  }

  function consumeList(startIndex) {
    const items = [];
    const firstLine = lines[startIndex].trim();
    const ordered = /^\d+\.\s+/.test(firstLine);
    let cursor = startIndex;
    while (cursor < lines.length) {
      const line = lines[cursor].trim();
      const match = ordered ? line.match(/^\d+\.\s+(.*)$/) : line.match(/^([*-])\s+(.*)$/);
      if (!match) {
        break;
      }
      items.push(`<li>${renderInline(ordered ? match[1] : match[2])}</li>`);
      cursor += 1;
    }
    return {
      html: `<${ordered ? 'ol' : 'ul'}>${items.join('')}</${ordered ? 'ol' : 'ul'}>`,
      nextIndex: cursor,
    };
  }

  function consumeQuote(startIndex) {
    const quoteLines = [];
    let cursor = startIndex;
    while (cursor < lines.length) {
      const match = lines[cursor].match(/^>\s?(.*)$/);
      if (!match) {
        break;
      }
      quoteLines.push(match[1]);
      cursor += 1;
    }
    return {
      html: `<blockquote>${quoteLines.map(line => renderInline(line)).join('<br>')}</blockquote>`,
      nextIndex: cursor,
    };
  }

  while (index < lines.length) {
    const rawLine = lines[index];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(=+)\s*(.*?)\s*\1$/);
    if (headingMatch) {
      flushSection();
      const level = Math.min(4, Math.max(2, headingMatch[1].length));
      currentSection.push(`<h${level}>${renderInline(headingMatch[2])}</h${level}>`);
      index += 1;
      continue;
    }

    const codeMatch = trimmed.match(/^```([^`]*)$/);
    if (codeMatch) {
      const language = codeMatch[1].trim();
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index].trim())) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      const codeClass = language ? ` class="language-${escapeHtml(language)}"` : '';
      currentSection.push(`<pre><code${codeClass}>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
      continue;
    }

    const dropdownMatch = trimmed.match(/^\{\{dropdown\s+(.+)\}\}$/i);
    if (dropdownMatch) {
      const title = dropdownMatch[1].trim();
      const innerLines = [];
      index += 1;
      while (index < lines.length) {
        const innerTrimmed = lines[index].trim();
        if (/^\{\{\/dropdown\}\}$/i.test(innerTrimmed) || /^\{\{end\}\}$/i.test(innerTrimmed)) {
          break;
        }
        innerLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      const innerHtml = renderWiki(innerLines.join('\n'), false);
      currentSection.push(`<details><summary>${renderInline(title)}</summary>${innerHtml}</details>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      currentSection.push('<hr>');
      index += 1;
      continue;
    }

    if (/^([*-])\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      const listResult = consumeList(index);
      currentSection.push(listResult.html);
      index = listResult.nextIndex;
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteResult = consumeQuote(index);
      currentSection.push(quoteResult.html);
      index = quoteResult.nextIndex;
      continue;
    }

    const paragraphResult = consumeParagraph(index);
    currentSection.push(paragraphResult.html);
    index = paragraphResult.nextIndex;
  }

  flushSection();

  if (!sections.length) {
    return wrapSections
      ? '<div class="section"><div class="codeblock">This page is empty. Press Edit to create content.</div></div>'
      : '';
  }

  return wrapSections
    ? sections.map(section => `<div class="section">${section}</div>`).join('')
    : sections.join('');
}

function childNodesToWiki(node) {
  return Array.from(node.childNodes).map(child => nodeToWiki(child)).filter(Boolean).join('');
}

function nodeToWiki(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.nodeValue.replace(/\s+/g, ' ');
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return '';
  }

  const tag = node.tagName.toLowerCase();
  if (tag === 'br') {
    return '\n';
  }
  if (tag === 'hr') {
    return '\n---\n';
  }
  if (tag === 'strong' || tag === 'b') {
    return `'''${childNodesToWiki(node).trim()}'''`;
  }
  if (tag === 'em' || tag === 'i') {
    return `''${childNodesToWiki(node).trim()}''`;
  }
  if (tag === 'del' || tag === 's' || tag === 'strike') {
    return `~~${childNodesToWiki(node).trim()}~~`;
  }
  if (tag === 'sub') {
    return `{{sub|${childNodesToWiki(node).trim()}}}`;
  }
  if (tag === 'code' && node.parentElement && node.parentElement.tagName.toLowerCase() !== 'pre') {
    return `\`${node.textContent}\``;
  }
  if (tag === 'a') {
    const href = sanitizeUrl(node.getAttribute('href') || '');
    const label = childNodesToWiki(node).trim() || node.textContent.trim();
    if (!href) {
      return label;
    }
    return `[${label}](${href})`;
  }
  if (tag === 'img') {
    const alt = node.getAttribute('alt') || '';
    const src = sanitizeUrl(node.getAttribute('src') || '');
    return src ? `[${alt || src}](${src})` : alt;
  }
  if (tag === 'pre') {
    const codeNode = node.querySelector('code');
    const languageClass = codeNode ? Array.from(codeNode.classList).find(className => className.startsWith('language-')) : '';
    const language = languageClass ? languageClass.replace('language-', '') : '';
    const codeText = (codeNode ? codeNode.textContent : node.textContent).replace(/\n$/, '');
    return `\n\`\`\`${language}\n${codeText}\n\`\`\`\n`;
  }
  if (tag === 'blockquote') {
    const lines = childNodesToWiki(node).split('\n').map(line => line.trim()).filter(Boolean);
    return lines.map(line => `> ${line}`).join('\n');
  }
  if (tag === 'ul' || tag === 'ol') {
    const prefix = tag === 'ol' ? '1.' : '*';
    return Array.from(node.children)
      .map(li => `${prefix} ${childNodesToWiki(li).trim()}`)
      .join('\n');
  }
  if (tag === 'li') {
    return childNodesToWiki(node).trim();
  }
  if (tag === 'details') {
    const summary = node.querySelector('summary');
    const summaryText = summary ? childNodesToWiki(summary).trim() : 'Dropdown';
    const contentNodes = Array.from(node.childNodes).filter(child => !(child.nodeType === Node.ELEMENT_NODE && child.tagName.toLowerCase() === 'summary'));
    const content = contentNodes.map(child => nodeToWiki(child)).filter(Boolean).join('\n').trim();
    return `{{dropdown ${summaryText}}}\n${content}\n{{/dropdown}}`;
  }
  if (tag === 'section' || tag === 'article' || tag === 'div' || tag === 'p') {
    if (node.classList.contains('codeblock')) {
      return `\n\`\`\`\n${node.textContent.trim()}\n\`\`\`\n`;
    }

    if (tag === 'div' && node.classList.contains('section')) {
      return Array.from(node.childNodes).map(child => nodeToWiki(child)).filter(Boolean).join('\n\n');
    }

    const styleColor = node.style && node.style.color ? node.style.color : '';
    const inner = childNodesToWiki(node).trim();
    if (tag === 'p') {
      return inner;
    }
    if (styleColor) {
      return `{{color:${styleColor}|${inner}}}`;
    }
    return inner;
  }
  if (/^h[1-6]$/.test(tag)) {
    const level = Math.min(6, Math.max(1, Number(tag.slice(1)) || 1));
    const equals = '='.repeat(level);
    return `${equals} ${childNodesToWiki(node).trim()} ${equals}`;
  }
  if (tag === 'span') {
    const styleColor = node.style && node.style.color ? node.style.color : '';
    const inner = childNodesToWiki(node).trim();
    if (styleColor) {
      return `{{color:${styleColor}|${inner}}}`;
    }
    return inner;
  }
  if (tag === 'sup') {
    return `^${childNodesToWiki(node).trim()}`;
  }

  return Array.from(node.childNodes).map(child => nodeToWiki(child)).filter(Boolean).join('');
}

function htmlToWiki(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div id="wiki-root">${html}</div>`, 'text/html');
  const root = doc.getElementById('wiki-root');
  if (!root) {
    return '';
  }

  const parts = Array.from(root.childNodes).map(node => nodeToWiki(node)).filter(Boolean);
  return parts.join('\n\n').replace(/\n{3,}/g, '\n\n').trim();
}

async function loadWikiSource(page, fallbackHtml) {
  const fallbackText = String(fallbackHtml || '');
  if (fallbackText.includes('This page is empty. Press Edit to create content.') || fallbackText.includes('Failed to load page.')) {
    return '';
  }
  try {
    const res = await fetch(`./pages/${page}.wiki?t=${Date.now()}`);
    if (res.ok) {
      return await res.text();
    }
  } catch (error) {
    // Fall back to converting the current page HTML.
  }
  return htmlToWiki(fallbackHtml);
}

function setEditingMode(isEditing) {
  editorPanel.hidden = !isEditing;
  pageEl.hidden = isEditing;
  saveBtn.style.display = isEditing ? '' : 'none';
  cancelBtn.style.display = isEditing ? '' : 'none';
  editBtn.textContent = isEditing ? 'Done' : 'Edit';
  editBtn.setAttribute('aria-pressed', isEditing ? 'true' : 'false');
}

function closeEditor(discardChanges = true) {
  if (discardChanges) {
    sourceEditor.value = originalSource;
    pageEl.innerHTML = originalHtml;
  }
  isEditing = false;
  pageEl.classList.remove('editable');
  setEditingMode(false);
}

function updatePreview() {
  if (!previewPage || !sourceEditor) {
    return;
  }
  previewPage.innerHTML = renderWiki(sourceEditor.value, true);
}

function insertSourceText(text, selectStartOffset = 0, selectEndOffset = 0) {
  const start = sourceEditor.selectionStart;
  const end = sourceEditor.selectionEnd;
  const value = sourceEditor.value;
  const nextValue = `${value.slice(0, start)}${text}${value.slice(end)}`;
  sourceEditor.value = nextValue;
  const selectionStart = start + selectStartOffset;
  const selectionEnd = start + selectEndOffset;
  sourceEditor.focus();
  sourceEditor.setSelectionRange(selectionStart, selectionEnd);
  updatePreview();
}

function wrapSelection(prefix, suffix = prefix, fallback = 'text') {
  const start = sourceEditor.selectionStart;
  const end = sourceEditor.selectionEnd;
  const value = sourceEditor.value;
  const selected = value.slice(start, end) || fallback;
  const nextValue = `${value.slice(0, start)}${prefix}${selected}${suffix}${value.slice(end)}`;
  sourceEditor.value = nextValue;
  sourceEditor.focus();
  sourceEditor.setSelectionRange(start + prefix.length, start + prefix.length + selected.length);
  updatePreview();
}

function prefixCurrentLines(prefix) {
  const start = sourceEditor.selectionStart;
  const end = sourceEditor.selectionEnd;
  const value = sourceEditor.value;
  const selection = value.slice(start, end) || '';
  const target = selection || 'Item';
  const transformed = target.split('\n').map(line => `${prefix}${line}`).join('\n');
  const nextValue = `${value.slice(0, start)}${transformed}${value.slice(end)}`;
  sourceEditor.value = nextValue;
  sourceEditor.focus();
  sourceEditor.setSelectionRange(start, start + transformed.length);
  updatePreview();
}

function promptAndInsertLink() {
  const selected = sourceEditor.value.slice(sourceEditor.selectionStart, sourceEditor.selectionEnd).trim();
  const label = window.prompt('Link text', selected || 'link text');
  if (!label) {
    return;
  }
  const url = window.prompt('Link URL', 'https://');
  if (!url) {
    return;
  }
  insertSourceText(`[${label}](${url})`, 1, 1 + label.length);
}

function promptAndInsertColor() {
  const selected = sourceEditor.value.slice(sourceEditor.selectionStart, sourceEditor.selectionEnd).trim();
  const color = window.prompt('Text color', '#c05c2f');
  if (!color) {
    return;
  }
  wrapSelection(`{{color:${color}|`, '}}', selected || 'colored text');
}

function promptAndInsertDropdown() {
  const title = window.prompt('Dropdown title', 'More info');
  if (!title) {
    return;
  }
  const template = `{{dropdown ${title}}}\nDropdown content\n{{/dropdown}}`;
  const start = sourceEditor.selectionStart;
  const end = sourceEditor.selectionEnd;
  const value = sourceEditor.value;
  const nextValue = `${value.slice(0, start)}${template}${value.slice(end)}`;
  sourceEditor.value = nextValue;
  sourceEditor.focus();
  sourceEditor.setSelectionRange(start + template.indexOf('Dropdown content'), start + template.indexOf('Dropdown content') + 'Dropdown content'.length);
  updatePreview();
}

function promptAndInsertCode() {
  const language = window.prompt('Code language (optional)', '');
  const start = sourceEditor.selectionStart;
  const end = sourceEditor.selectionEnd;
  const selected = sourceEditor.value.slice(start, end).trim() || 'code here';
  const template = `\`\`\`${language || ''}\n${selected}\n\`\`\``;
  const nextValue = `${sourceEditor.value.slice(0, start)}${template}${sourceEditor.value.slice(end)}`;
  sourceEditor.value = nextValue;
  sourceEditor.focus();
  sourceEditor.setSelectionRange(start + template.indexOf(selected), start + template.indexOf(selected) + selected.length);
  updatePreview();
}

function promptAndInsertHeader() {
  const selected = sourceEditor.value.slice(sourceEditor.selectionStart, sourceEditor.selectionEnd).trim();
  const heading = window.prompt('Header text', selected || 'Section title');
  if (!heading) {
    return;
  }
  insertSourceText(`== ${heading} ==\n\n`, 3, 3 + heading.length);
}

function formatPageTitle(page) {
  return page.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

async function loadPage(page){
  currentPage = page;
  currentSource = '';
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
  originalSource = '';
  if (previewPage) {
    previewPage.innerHTML = '';
  }
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

editorToolbar.addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button || !sourceEditor) {
    return;
  }

  const action = button.dataset.action;
  if (action === 'bold') {
    wrapSelection("'''", "'''", 'bold text');
  } else if (action === 'italic') {
    wrapSelection("''", "''", 'italic text');
  } else if (action === 'header') {
    promptAndInsertHeader();
  } else if (action === 'link') {
    promptAndInsertLink();
  } else if (action === 'bullet') {
    prefixCurrentLines('* ');
  } else if (action === 'code') {
    promptAndInsertCode();
  } else if (action === 'dropdown') {
    promptAndInsertDropdown();
  } else if (action === 'color') {
    promptAndInsertColor();
  } else if (action === 'strike') {
    wrapSelection('~~', '~~', 'struck text');
  } else if (action === 'sub') {
    wrapSelection('{{sub|', '}}', 'subtext');
  } else if (action === 'hr') {
    insertSourceText('\n---\n\n', 1, 1);
  }
});

sourceEditor.addEventListener('input', updatePreview);

editBtn.addEventListener('click',async()=>{
  if (isEditing) {
    closeEditor(true);
    return;
  }

  if (!wikiEditToken) {
    alert('You need the Discord role edit link to save changes.');
    return;
  }
  if (!currentSource) {
    currentSource = await loadWikiSource(currentPage, originalHtml);
  }
  originalSource = currentSource;
  sourceEditor.value = currentSource;
  updatePreview();
  isEditing = true;
  setEditingMode(true);
});

cancelBtn.addEventListener('click',()=>{
  closeEditor(true);
});

saveBtn.addEventListener('click',async()=>{
  const source = sourceEditor.value;
  const body = renderWiki(source, true);
  try{
    const res = await fetch('/api/wiki/save',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({page: currentPage, source, html: body, edit_token: wikiEditToken})
    });
    if(res.ok){
      originalHtml = body;
      originalSource = source;
      currentSource = source;
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
