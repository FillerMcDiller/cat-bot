const pageEl = document.getElementById('page');
const editBtn = document.getElementById('editBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const navItems = document.querySelectorAll('.sidebar nav li');
const crumbPage = document.getElementById('crumbPage');
const articleHeading = document.getElementById('articleHeading');
const wikiEditToken = new URLSearchParams(window.location.search).get('edit') || '';
let currentPage = 'overview';
let originalHtml = '';

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
  pageEl.contentEditable = 'false';
  editBtn.style.display = '';
  saveBtn.style.display = 'none';
  cancelBtn.style.display = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navItems.forEach(li=>{
  li.addEventListener('click',()=>{
    navItems.forEach(i=>i.classList.remove('active'));
    li.classList.add('active');
    loadPage(li.dataset.page);
  })
});

editBtn.addEventListener('click',()=>{
  if (!wikiEditToken) {
    alert('You need the Discord role edit link to save changes.');
    return;
  }
  pageEl.contentEditable = 'true';
  pageEl.classList.add('editable');
  editBtn.style.display = 'none';
  saveBtn.style.display = '';
  cancelBtn.style.display = '';
});

cancelBtn.addEventListener('click',()=>{
  pageEl.innerHTML = originalHtml;
  pageEl.contentEditable = 'false';
  pageEl.classList.remove('editable');
  editBtn.style.display = '';
  saveBtn.style.display = 'none';
  cancelBtn.style.display = 'none';
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
      pageEl.contentEditable = 'false';
      pageEl.classList.remove('editable');
      editBtn.style.display = '';
      saveBtn.style.display = 'none';
      cancelBtn.style.display = 'none';
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
