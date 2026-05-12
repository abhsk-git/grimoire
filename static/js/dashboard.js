// ── Dashboard JS ─────────────────────────────────────────────
let state = {
  user: null, links: [], collections: [], tags: [],
  page: 1, total: 0, perPage: 20,
  query: '', currentView: 'all', currentCollection: null,
  currentTag: null, layout: 'grid', editingLinkId: null,
  selectedEmoji: '📁', selectedColor: '#6366f1',
  fetchedMeta: null, searchTimer: null
};

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuth();
  await Promise.all([loadCollections(), loadTags(), loadStats()]);
  loadLinks();
});

async function checkAuth() {
  const r = await fetch('/api/auth/me', { credentials: 'include' });
  if (!r.ok) { window.location.href = '/'; return; }
  state.user = await r.json();
  document.getElementById('userName').textContent = state.user.name;
  document.getElementById('userEmail').textContent = state.user.email;
  document.getElementById('userAvatar').src = state.user.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(state.user.name)}&background=6366f1&color=fff`;
}

// ── Load Links ────────────────────────────────────────────────
async function loadLinks(reset = true) {
  if (reset) { state.page = 1; state.links = []; }
  const params = new URLSearchParams({
    q: state.query, page: state.page, per_page: state.perPage
  });
  if (state.currentView === 'public') params.set('public', '1');
  if (state.currentView === 'private') params.set('public', '0');
  if (state.currentCollection) params.set('collection', state.currentCollection);
  if (state.currentTag) params.set('tag', state.currentTag);

  const r = await fetch('/api/links?' + params, { credentials: 'include' });
  const data = await r.json();
  state.links = reset ? data.links : [...state.links, ...data.links];
  state.total = data.total;
  renderLinks();
  document.getElementById('linksCount').textContent = `${state.total} link${state.total !== 1 ? 's' : ''}`;
  document.getElementById('loadMoreWrap').classList.toggle('hidden', state.links.length >= state.total);
}

function loadMore() { state.page++; loadLinks(false); }

function renderLinks() {
  const grid = document.getElementById('linksGrid');
  const empty = document.getElementById('emptyState');
  if (!state.links.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  grid.className = 'links-grid' + (state.layout === 'list' ? ' list-layout' : '');
  grid.innerHTML = state.links.map(buildCard).join('');
}

function buildCard(link) {
  const domain = (() => { try { return new URL(link.url).hostname.replace('www.',''); } catch { return ''; } })();
  const tags = link.tags ? link.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
  const date = new Date(link.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  const colBadge = link.collection_name ? `<span class="col-badge" style="background:${link.collection_color}22;color:${link.collection_color}">${link.collection_name}</span>` : '';

  const imgHtml = link.image
    ? `<img class="card-image" src="${esc(link.image)}" alt="" onerror="this.style.display='none'">`
    : `<div class="card-image no-img">${getDomainEmoji(domain)}</div>`;

  return `
  <div class="link-card" data-id="${link.id}">
    <span class="${link.is_public ? 'badge-public' : 'badge-private'}">${link.is_public ? '🌐 Public' : '🔒 Private'}</span>
    ${state.layout !== 'list' ? imgHtml : ''}
    <div class="card-body">
      <div class="card-top">
        <img class="card-favicon" src="${esc(link.favicon || '')}" onerror="this.style.display='none'" alt="">
        <span class="card-domain">${esc(domain)}</span>
        ${colBadge}
      </div>
      <div class="card-title">${esc(link.title || domain || 'Untitled')}</div>
      ${link.description ? `<div class="card-desc">${esc(link.description)}</div>` : ''}
      ${tags.length ? `<div class="card-tags">${tags.map(t => `<span class="card-tag" onclick="filterTag('${esc(t)}',event)">#${esc(t)}</span>`).join('')}</div>` : ''}
      <div class="card-footer">
        <span class="card-meta">${date}${link.visit_count ? ` · ${link.visit_count} visits` : ''}</span>
        <div class="card-actions">
          <button class="btn-icon" onclick="openLink(${link.id},'${esc(link.url)}',event)" title="Open">↗</button>
          <button class="btn-icon" onclick="editLink(${link.id},event)" title="Edit">✏</button>
          <button class="btn-icon" onclick="deleteLink(${link.id},event)" title="Delete" style="color:var(--danger)">🗑</button>
        </div>
      </div>
    </div>
  </div>`;
}

function getDomainEmoji(domain) {
  if (!domain) return '🔗';
  if (domain.includes('github')) return '🐙';
  if (domain.includes('youtube')) return '▶️';
  if (domain.includes('twitter') || domain.includes('x.com')) return '🐦';
  if (domain.includes('medium')) return '📰';
  if (domain.includes('reddit')) return '🤖';
  if (domain.includes('stackoverflow')) return '💬';
  if (domain.includes('notion')) return '📓';
  if (domain.includes('figma')) return '🎨';
  return '🔗';
}

// ── Link Actions ──────────────────────────────────────────────
async function openLink(id, url, e) {
  e.stopPropagation();
  await fetch(`/api/links/${id}/visit`, { method: 'POST', credentials: 'include' });
  window.open(url, '_blank', 'noopener');
  const link = state.links.find(l => l.id === id);
  if (link) link.visit_count = (link.visit_count || 0) + 1;
}

async function deleteLink(id, e) {
  e.stopPropagation();
  if (!confirm('Delete this link?')) return;
  await fetch(`/api/links/${id}`, { method: 'DELETE', credentials: 'include' });
  state.links = state.links.filter(l => l.id !== id);
  state.total--;
  renderLinks();
  loadStats();
  showToast('Link deleted', 'success');
}

function editLink(id, e) {
  e.stopPropagation();
  const link = state.links.find(l => l.id === id);
  if (!link) return;
  state.editingLinkId = id;
  state.fetchedMeta = null;
  document.getElementById('modalTitle').textContent = 'Edit Link';
  document.getElementById('linkUrl').value = link.url;
  document.getElementById('linkTitle').value = link.title || '';
  document.getElementById('linkDesc').value = link.description || '';
  document.getElementById('linkTags').value = link.tags || '';
  document.getElementById('linkCollection').value = link.collection_id || '';
  document.getElementById('linkNotes').value = link.notes || '';
  document.getElementById('visPrivate').checked = !link.is_public;
  document.getElementById('visPublic').checked = !!link.is_public;
  document.getElementById('fetchPreview').classList.add('hidden');
  openModal('linkModal');
}

// ── Add / Save Link ───────────────────────────────────────────
function openAddModal() {
  state.editingLinkId = null; state.fetchedMeta = null;
  document.getElementById('modalTitle').textContent = 'Add Link';
  document.getElementById('linkUrl').value = '';
  document.getElementById('linkTitle').value = '';
  document.getElementById('linkDesc').value = '';
  document.getElementById('linkTags').value = '';
  document.getElementById('linkCollection').value = '';
  document.getElementById('linkNotes').value = '';
  document.getElementById('visPrivate').checked = true;
  document.getElementById('fetchPreview').classList.add('hidden');
  openModal('linkModal');
  renderTagSuggestions();
  setTimeout(() => document.getElementById('linkUrl').focus(), 100);
}

function onUrlInput() {
  const url = document.getElementById('linkUrl').value;
  document.getElementById('fetchBtn').style.opacity = url ? '1' : '0.5';
}

async function fetchMeta() {
  const url = document.getElementById('linkUrl').value.trim();
  if (!url) return;
  const btn = document.getElementById('fetchBtn');
  btn.textContent = '⏳'; btn.disabled = true;
  try {
    const r = await fetch('/api/fetch-meta', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const meta = await r.json();
    state.fetchedMeta = meta;
    if (meta.title) document.getElementById('linkTitle').value = meta.title;
    if (meta.description) document.getElementById('linkDesc').value = meta.description;
    if (meta.favicon) {
      document.getElementById('previewFavicon').src = meta.favicon;
      document.getElementById('fetchPreview').classList.remove('hidden');
      const domain = (() => { try { return new URL(meta.url || url).hostname.replace('www.',''); } catch { return url; } })();
      document.getElementById('previewDomain').textContent = domain;
    }
    showToast('Metadata fetched!', 'success');
  } catch { showToast('Could not fetch metadata', 'error'); }
  finally { btn.textContent = '⚡ Fetch'; btn.disabled = false; }
}

async function saveLink() {
  const url = document.getElementById('linkUrl').value.trim();
  if (!url) { showToast('URL is required', 'error'); return; }

  const payload = {
    url, title: document.getElementById('linkTitle').value.trim(),
    description: document.getElementById('linkDesc').value.trim(),
    tags: document.getElementById('linkTags').value.trim(),
    collection_id: document.getElementById('linkCollection').value || null,
    is_public: document.getElementById('visPublic').checked,
    notes: document.getElementById('linkNotes').value.trim(),
    image: state.fetchedMeta?.image || '',
    favicon: state.fetchedMeta?.favicon || ''
  };

  const savBtn = document.getElementById('saveLinkBtn');
  savBtn.textContent = 'Saving…'; savBtn.disabled = true;
  try {
    let r, data;
    if (state.editingLinkId) {
      r = await fetch(`/api/links/${state.editingLinkId}`, {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    } else {
      r = await fetch('/api/links', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    }
    if (!r.ok) { const d = await r.json(); showToast(d.error || 'Save failed', 'error'); return; }
    closeModal('linkModal');
    showToast(state.editingLinkId ? 'Link updated!' : 'Link saved!', 'success');
    await loadLinks();
    await loadTags();
    loadStats();
  } finally { savBtn.textContent = 'Save Link'; savBtn.disabled = false; }
}

// ── Collections ───────────────────────────────────────────────
async function loadCollections() {
  const r = await fetch('/api/collections', { credentials: 'include' });
  state.collections = await r.json();
  renderCollections();
  renderCollectionSelect();
}

function renderCollections() {
  const el = document.getElementById('collectionsList');
  el.innerHTML = state.collections.map(c => `
    <div class="col-item ${state.currentCollection == c.id ? 'active' : ''}" onclick="filterCollection(${c.id})">
      <span class="col-icon">${c.icon}</span>
      <span class="col-name">${esc(c.name)}</span>
      <span class="col-count">${c.link_count}</span>
      <button class="col-del" onclick="deleteCollection(${c.id},event)">✕</button>
    </div>`).join('') || '<div class="loading-sm">No collections yet</div>';
}

function renderCollectionSelect() {
  const sel = document.getElementById('linkCollection');
  const cur = sel.value;
  sel.innerHTML = '<option value="">— None —</option>' +
    state.collections.map(c => `<option value="${c.id}">${c.icon} ${esc(c.name)}</option>`).join('');
  if (cur) sel.value = cur;
}

function openNewCollection() { openModal('colModal'); }

async function saveCollection() {
  const name = document.getElementById('colName').value.trim();
  if (!name) { showToast('Name required', 'error'); return; }
  await fetch('/api/collections', {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, icon: state.selectedEmoji, color: state.selectedColor })
  });
  document.getElementById('colName').value = '';
  closeModal('colModal');
  await loadCollections();
  showToast('Collection created!', 'success');
}

async function deleteCollection(id, e) {
  e.stopPropagation();
  if (!confirm('Delete this collection? Links inside will be unassigned.')) return;
  await fetch(`/api/collections/${id}`, { method: 'DELETE', credentials: 'include' });
  if (state.currentCollection == id) { state.currentCollection = null; state.currentView = 'all'; }
  await loadCollections();
  await loadLinks();
  showToast('Collection deleted', 'success');
}

function selectEmoji(el) {
  document.querySelectorAll('.emoji-opt').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  state.selectedEmoji = el.textContent;
}
function selectColor(el) {
  document.querySelectorAll('.color-swatch').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  state.selectedColor = el.dataset.color;
}

// ── Tags ──────────────────────────────────────────────────────
async function loadTags() {
  const r = await fetch('/api/tags', { credentials: 'include' });
  state.tags = await r.json();
  renderTagCloud();
}

function renderTagCloud() {
  document.getElementById('tagsList').innerHTML = state.tags.slice(0, 20).map(t =>
    `<span class="tag-pill ${state.currentTag === t.name ? 'active' : ''}" onclick="filterTag('${esc(t.name)}')">#${esc(t.name)} <small>${t.count}</small></span>`
  ).join('');
}

function renderTagSuggestions() {
  const el = document.getElementById('tagSuggestions');
  el.innerHTML = state.tags.slice(0, 12).map(t =>
    `<span class="tag-sug" onclick="addTag('${esc(t.name)}')">#${esc(t.name)}</span>`
  ).join('');
}

function addTag(tag) {
  const el = document.getElementById('linkTags');
  const existing = el.value.split(',').map(t => t.trim()).filter(Boolean);
  if (!existing.includes(tag)) {
    el.value = [...existing, tag].join(', ');
  }
}

// ── Filters & Views ───────────────────────────────────────────
function setView(view) {
  state.currentView = view; state.currentCollection = null; state.currentTag = null;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === view);
  });
  document.querySelectorAll('.col-item, .tag-pill').forEach(el => el.classList.remove('active'));
  const titles = { all: 'All Links', public: 'Public Links', private: 'Private Links' };
  document.getElementById('linksTitle').textContent = titles[view] || 'Links';
  loadLinks();
}

function filterCollection(id) {
  state.currentCollection = id; state.currentView = 'all'; state.currentTag = null;
  state.query = ''; document.getElementById('searchInput').value = '';
  const col = state.collections.find(c => c.id === id);
  document.getElementById('linksTitle').textContent = col ? `${col.icon} ${col.name}` : 'Collection';
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  renderCollections();
  document.querySelectorAll('.tag-pill').forEach(el => el.classList.remove('active'));
  loadLinks();
}

function filterTag(tag, e) {
  if (e) e.stopPropagation();
  if (state.currentTag === tag) { state.currentTag = null; }
  else { state.currentTag = tag; state.currentCollection = null; }
  document.getElementById('linksTitle').textContent = state.currentTag ? `#${state.currentTag}` : 'All Links';
  renderTagCloud();
  loadLinks();
}

function onSearch(val) {
  clearTimeout(state.searchTimer);
  state.query = val;
  document.getElementById('searchClear').classList.toggle('hidden', !val);
  state.searchTimer = setTimeout(() => loadLinks(), 350);
}
function clearSearch() {
  document.getElementById('searchInput').value = '';
  state.query = '';
  document.getElementById('searchClear').classList.add('hidden');
  loadLinks();
}

function setLayout(layout) {
  state.layout = layout;
  document.getElementById('gridBtn').classList.toggle('active', layout === 'grid');
  document.getElementById('listBtn').classList.toggle('active', layout === 'list');
  renderLinks();
}

// ── Stats ─────────────────────────────────────────────────────
async function loadStats() {
  const r = await fetch('/api/stats', { credentials: 'include' });
  const s = await r.json();
  document.getElementById('statTotal').textContent = s.total;
  document.getElementById('statPublic').textContent = s.public_count;
  document.getElementById('statVisits').textContent = s.total_visits;
  document.getElementById('statCols').textContent = s.collections;
}

// ── Profile ───────────────────────────────────────────────────
function openProfile() {
  hideUserMenu();
  document.getElementById('profileAvatar').src = state.user.avatar || '';
  document.getElementById('profileNameDisplay').textContent = state.user.name;
  document.getElementById('profileEmailDisplay').textContent = state.user.email;
  document.getElementById('profileName').value = state.user.name;
  document.getElementById('profileBio').value = state.user.bio || '';
  openModal('profileModal');
}

async function saveProfile() {
  const name = document.getElementById('profileName').value.trim();
  const bio = document.getElementById('profileBio').value.trim();
  await fetch('/api/profile', {
    method: 'PUT', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, bio })
  });
  state.user.name = name; state.user.bio = bio;
  document.getElementById('userName').textContent = name;
  closeModal('profileModal');
  showToast('Profile updated!', 'success');
}

// ── Auth ──────────────────────────────────────────────────────
async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  window.location.href = '/';
}

// ── UI Helpers ────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
  document.getElementById(id + 'Overlay').classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
  document.getElementById(id + 'Overlay').classList.add('hidden');
}
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  if (window.innerWidth <= 768) { sb.classList.toggle('mobile-open'); }
  else { sb.classList.toggle('collapsed'); }
}
function toggleUserMenu() { document.getElementById('userMenu').classList.toggle('hidden'); }
function hideUserMenu() { document.getElementById('userMenu').classList.add('hidden'); }

document.addEventListener('click', e => {
  if (!e.target.closest('.sidebar-footer')) hideUserMenu();
});

function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (type ? ' ' + type : '');
  t.classList.remove('hidden');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), 2800);
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// Enter to save link
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeModal('linkModal'); closeModal('colModal'); closeModal('profileModal');
  }
});