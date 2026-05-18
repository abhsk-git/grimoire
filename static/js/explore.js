// ── Explore JS — dual mode (Links + Blog) ────────────────────
let mode = typeof _initMode !== 'undefined' ? _initMode : 'links';

let linksState = { items: [], page: 1, total: 0, perPage: 24, query: '', activeTag: _initTag || null, timer: null };
let blogState  = { items: [], page: 1, total: 0, perPage: 12, query: '', activeTag: _initTag || null, timer: null };

document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  switchMode(mode, true);
});

// ── Auth check ────────────────────────────────────────────────
async function checkAuth() {
  try {
    const r = await fetch('/api/auth/me', { credentials: 'include' });
    const nav   = document.getElementById('exploreNavAuth');
    const write = document.getElementById('writeBtn');
    if (r.ok) {
      nav.innerHTML = `<a href="/dashboard" class="btn-primary">My Dashboard <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></a>`;
      if (write) write.classList.remove('hidden');
    } else {
      nav.innerHTML = `<button class="btn-primary" onclick="showPanel('login')">Login</button>`;
    }
  } catch {}
}

// ── Mode switching ────────────────────────────────────────────
function switchMode(newMode, initial = false) {
  mode = newMode;
  document.getElementById('tab-links').classList.toggle('active', mode === 'links');
  document.getElementById('tab-blog').classList.toggle('active',  mode === 'blog');

  const search = document.getElementById('exploreSearch');
  if (mode === 'links') {
    search.placeholder = 'Search links…';
    document.getElementById('trendingLabel').textContent = 'Trending link tags';
    setEmptyState('No public links yet', 'Be the first to share something with the community', 'Add your links', () => showPanel('register'));
    loadTrendingTags();
    loadLinks(true);
  } else {
    search.placeholder = 'Search posts…';
    document.getElementById('trendingLabel').textContent = 'Popular post tags';
    setEmptyState('No blog posts yet', 'Be the first to share your story with the community', 'Start writing', () => { window.location.href = '/write'; });
    loadBlogTags();
    loadPosts(true);
  }

  // Update URL without reload
  if (!initial) {
    const params = new URLSearchParams({ mode });
    if (mode === 'links' && linksState.activeTag) params.set('tag', linksState.activeTag);
    if (mode === 'blog'  && blogState.activeTag)  params.set('tag', blogState.activeTag);
    history.replaceState(null, '', `?${params}`);
  }
}

function setEmptyState(title, desc, btnText, btnFn) {
  document.getElementById('emptyTitle').textContent  = title;
  document.getElementById('emptyDesc').textContent   = desc;
  const btn = document.getElementById('emptyAction');
  btn.textContent = btnText;
  btn.onclick     = btnFn;
}

// ── LINKS mode ────────────────────────────────────────────────
async function loadLinks(reset = true) {
  if (reset) { linksState.page = 1; linksState.items = []; }
  const p = new URLSearchParams({ q: linksState.query, page: linksState.page, per_page: linksState.perPage });
  if (linksState.activeTag) p.set('tag', linksState.activeTag);
  const r = await fetch('/api/explore?' + p);
  const data = await r.json();
  linksState.items = reset ? data.links : [...linksState.items, ...data.links];
  linksState.total = data.total;
  renderGrid(linksState.items.map(buildLinkCard));
  document.getElementById('exploreLoadMore').classList.toggle('hidden', linksState.items.length >= linksState.total);
}

async function loadTrendingTags() {
  const r    = await fetch('/api/explore/trending-tags');
  const tags = await r.json();
  renderTags(tags, linksState.activeTag, tag => filterByTag(tag, 'links'));
}

function buildLinkCard(link) {
  const domain  = (() => { try { return new URL(link.url).hostname.replace('www.',''); } catch { return ''; } })();
  const tags    = link.tags ? link.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
  const date    = new Date(link.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  const initial = domain ? domain[0].toUpperCase() : '?';
  return `
  <div class="link-card" onclick="openLink('${esc(link.url)}', ${link.id})">
    <div class="card-media ${link.image ? '' : 'card-media--empty'}">
      ${link.image
        ? `<img class="card-image" src="${esc(link.image)}" alt="" onerror="this.parentElement.classList.add('card-media--empty');this.parentElement.insertAdjacentHTML('afterbegin','<div class=\\'domain-initial\\'>${initial}</div>');this.remove()">`
        : `<div class="domain-initial">${initial}</div>`}
    </div>
    <div class="card-body">
      <div class="card-top">
        <img class="card-favicon" src="${esc(link.favicon||'')}" onerror="this.style.display='none'" alt="">
        <span class="card-domain">${esc(domain)}</span>
      </div>
      <div class="card-title">${esc(link.title || domain || 'Untitled')}</div>
      ${link.description ? `<div class="card-desc">${esc(link.description)}</div>` : ''}
      ${tags.length ? `<div class="card-tags">${tags.slice(0,3).map(t=>`<span class="card-tag" onclick="filterByTag('${esc(t)}','links',event)">#${esc(t)}</span>`).join('')}</div>` : ''}
      <div class="card-author">
        <img src="${esc(link.author_avatar||'')}" alt="" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(link.author_name||'?')}&size=32&background=6366f1&color=fff'">
        <span>${esc(link.author_name||'Anonymous')} · ${date}</span>
        ${link.visit_count ? `<span class="view-count">${link.visit_count} views</span>` : ''}
      </div>
    </div>
  </div>`;
}

function openLink(url, id) { window.open(url, '_blank', 'noopener'); }

// ── BLOG mode ─────────────────────────────────────────────────
async function loadPosts(reset = true) {
  if (reset) { blogState.page = 1; blogState.items = []; }
  const p = new URLSearchParams({ q: blogState.query, page: blogState.page, per_page: blogState.perPage });
  if (blogState.activeTag) p.set('tag', blogState.activeTag);
  const r = await fetch('/api/blog/posts?' + p);
  const data = await r.json();
  blogState.items = reset ? data.posts : [...blogState.items, ...data.posts];
  blogState.total = data.total;
  renderGrid(blogState.items.map(buildBlogCard));
  document.getElementById('exploreLoadMore').classList.toggle('hidden', blogState.items.length >= blogState.total);
}

async function loadBlogTags() {
  const r    = await fetch('/api/blog/tags');
  const tags = await r.json();
  renderTags(tags, blogState.activeTag, tag => filterByTag(tag, 'blog'));
}

function buildBlogCard(post) {
  const tags = post.tags ? post.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
  return `
  <div class="blog-card" onclick="window.location.href='/blog/${esc(post.slug)}'">
    <div class="blog-card-cover">
      ${post.cover_image
        ? `<img src="${esc(post.cover_image)}" alt="${esc(post.title)}" onerror="this.parentElement.innerHTML='<div class=\\'blog-card-cover-placeholder\\'>✍️</div>'">`
        : `<div class="blog-card-cover-placeholder">✍️</div>`}
      <div class="blog-card-badges">
        <span class="badge-blog">Blog</span>
        <span class="badge-read-time">⏱ ${post.reading_time} min</span>
      </div>
    </div>
    <div class="blog-card-body">
      ${tags.length ? `<div class="blog-card-tags">${tags.slice(0,3).map(t=>`<span class="blog-card-tag" onclick="filterByTag('${esc(t)}','blog',event)">#${esc(t)}</span>`).join('')}</div>` : ''}
      <div class="blog-card-title">${esc(post.title)}</div>
      ${post.excerpt ? `<div class="blog-card-excerpt">${esc(post.excerpt)}</div>` : ''}
      <div class="blog-card-footer">
        <img src="${esc(post.author_avatar||'')}" alt=""
          onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(post.author_name||'?')}&size=22&background=6366f1&color=fff'">
        <span class="author-text">${esc(post.author_name||'Anonymous')} · ${post.pub_date||''}</span>
        <span class="blog-card-likes">♥ ${post.likes||0}</span>
      </div>
    </div>
  </div>`;
}

// ── Load more ─────────────────────────────────────────────────
function exploreLoadMore() {
  if (mode === 'links') { linksState.page++; loadLinks(false); }
  else                  { blogState.page++;  loadPosts(false); }
}

// ── Tag filtering ─────────────────────────────────────────────
function filterByTag(tag, targetMode, e) {
  if (e) e.stopPropagation();
  if (targetMode) switchMode(targetMode);
  const st = mode === 'links' ? linksState : blogState;
  st.activeTag = st.activeTag === tag ? null : tag;
  document.querySelectorAll('.trend-tag').forEach(el => {
    el.classList.toggle('active', el.textContent.trim().startsWith('#' + tag));
  });
  mode === 'links' ? loadLinks() : loadPosts();
}

// ── Trending tags render ──────────────────────────────────────
function renderTags(tags, activeTag, onTagClick) {
  document.getElementById('trendingTags').innerHTML = tags.map(t =>
    `<span class="trend-tag ${activeTag === t.name ? 'active' : ''}" onclick="(${onTagClick.toString()})('${esc(t.name)}')">#${esc(t.name)} <span class="trend-count">${t.count}</span></span>`
  ).join('');
}

// ── Render grid ───────────────────────────────────────────────
function renderGrid(cards) {
  const grid  = document.getElementById('exploreGrid');
  const empty = document.getElementById('exploreEmpty');
  if (!cards.length) { grid.innerHTML = ''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  grid.innerHTML = cards.join('');
}

// ── Search ────────────────────────────────────────────────────
function onExploreSearch(val) {
  const st = mode === 'links' ? linksState : blogState;
  clearTimeout(st.timer);
  st.query = val;
  st.timer = setTimeout(() => mode === 'links' ? loadLinks() : loadPosts(), 350);
}

// ── Toast ─────────────────────────────────────────────────────
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (type ? ' '+type : '');
  t.classList.remove('hidden');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add('hidden'), 2800);
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
