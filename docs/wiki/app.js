const pageEl = document.getElementById('page');
const editBtn = document.getElementById('editBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const navItems = document.querySelectorAll('.sidebar nav li');
let currentPage = 'overview';
let originalHtml = '';

async function loadPage(page){
  currentPage = page;
  document.querySelector('.page-title').textContent = page.replace(/-/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
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
}

navItems.forEach(li=>{
  li.addEventListener('click',()=>{
    navItems.forEach(i=>i.classList.remove('active'));
    li.classList.add('active');
    loadPage(li.dataset.page);
  })
});

editBtn.addEventListener('click',()=>{
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
      body:JSON.stringify({page: currentPage, html: body})
    });
    if(res.ok){
      const data = await res.json();
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
loadPage(currentPage);
