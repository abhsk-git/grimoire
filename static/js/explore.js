// ── Explore JS ───────────────────────────────────────────────
let state = {
  links: [], page: 1, total: 0, perPage: 24,
  query: '', activeTag: null, searchTimer: null
};

document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  loadTrendingTags();
  loadExploreLinks();
});

async function checkAuth() {
  try {
    const r = await fetch('/api/auth/me', { credentials: 'include' });
    if (r.ok) {
      const user = await r.json();
      document.getElementById('exploreNavAuth').innerHTML =
        `<a href="/dashboard" class="btn-primary">My Dashboard →</a>`;
    }
  } catch {}
}

async function loadTrendingTags() {
  const r = await fetch('/api/explore/trending-tags');
  const tags = await r.json();
  document.getElementById('trendingTags').innerHTML = tags.map(t =>
    `<span class="trend-tag" onclick="filterByTag('${esc(t.name)}')">#${esc(t.name)} <span class="trend-count">${t.count}</span></span>`
  ).join('');
}

async function loadExploreLinks(reset = true) {
  if (reset) { state.page = 1; state.links = []; }
  const params = new URLSearchParams({ q: state.query, page: state.page, per_page: state.perPage });
  if (state.activeTag) params.set('tag', state.activeTag);

  const r = await fetch('/api/explore?' + params);
  const data = await r.json();
  state.links = reset ? data.links : [...state.links, ...data.links];
  state.total = data.total;
  document.getElementById('exploreTotal').textContent = state.total.toLocaleString();
  renderExplore();
  document.getElementById('exploreLoadMore').classList.toggle('hidden', state.links.length >= state.total);
}

function exploreLoadMore() { state.page++; loadExploreLinks(false); }

function renderExplore() {
  const grid = document.getElementById('exploreGrid');
  const empty = document.getElementById('exploreEmpty');
  if (!state.links.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  grid.innerHTML = state.links.map(buildExploreCard).join('');
}

function buildExploreCard(link) {
  const domain = (() => { try { return new URL(link.url).hostname.replace('www.',''); } catch { return ''; } })();
  const tags = link.tags ? link.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
  const date = new Date(link.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

  return `
  <div class="link-card" onclick="openLink('${esc(link.url)}', ${link.id})">
    ${link.image ? `<img class="card-image" src="${esc(link.image)}" alt="" onerror="this.style.display='none'">` : ''}
    <div class="card-body">
      <div class="card-top">
        <img class="card-favicon" src="${esc(link.favicon || '')}" onerror="this.style.display='none'" alt="">
        <span class="card-domain">${esc(domain)}</span>
      </div>
      <div class="card-title">${esc(link.title || domain || 'Untitled')}</div>
      ${link.description ? `<div class="card-desc">${esc(link.description)}</div>` : ''}
      ${tags.length ? `<div class="card-tags">${tags.map(t => `<span class="card-tag" onclick="filterByTag('${esc(t)}',event)">#${esc(t)}</span>`).join('')}</div>` : ''}
      <div class="card-author">
        <img src="${esc(link.author_avatar || '')}" alt="" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(link.author_name || '?')}&size=32&background=6366f1&color=fff'">
        <span>${esc(link.author_name || 'Anonymous')} · ${date}</span>
        ${link.visit_count ? `<span style="margin-left:auto;font-size:11px;color:var(--text3)">${link.visit_count} views</span>` : ''}
      </div>
    </div>
  </div>`;
}

function openLink(url, id) {
  window.open(url, '_blank', 'noopener');
}

function filterByTag(tag, e) {
  if (e) e.stopPropagation();
  state.activeTag = state.activeTag === tag ? null : tag;
  document.querySelectorAll('.trend-tag').forEach(el => {
    el.classList.toggle('active', el.textContent.trim().startsWith('#' + tag));
  });
  loadExploreLinks();
}

function onExploreSearch(val) {
  clearTimeout(state.searchTimer);
  state.query = val;
  state.searchTimer = setTimeout(() => loadExploreLinks(), 350);
}

function showToast(msg, type='') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (type ? ' '+type : '');
  t.classList.remove('hidden');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), 2800);
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}