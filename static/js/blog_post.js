// ── Blog Post Page ────────────────────────────────────────────
const SESSION_KEY = (() => {
  let k = localStorage.getItem('lv-session');
  if (!k) { k = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('lv-session', k); }
  return k;
})();

let liked = localStorage.getItem(`like-${POST_ID}`) === '1';

document.addEventListener('DOMContentLoaded', () => {
  loadComments();
  updateLikeUI();
  initReadProgress();
  Prism.highlightAll();
});

// ── Reading progress bar ──────────────────────────────────────
function initReadProgress() {
  const bar  = document.getElementById('readProgress');
  const body = document.body;
  document.addEventListener('scroll', () => {
    const h   = body.scrollHeight - window.innerHeight;
    const pct = h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 100;
    bar.style.width = pct + '%';
  }, { passive: true });
}

// ── Like ──────────────────────────────────────────────────────
async function toggleLike() {
  try {
    const r = await fetch(`/api/blog/posts/${POST_ID}/like`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_key: SESSION_KEY })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error);
    liked = data.action === 'liked';
    localStorage.setItem(`like-${POST_ID}`, liked ? '1' : '0');
    document.getElementById('topLikeCount').textContent    = data.likes;
    document.getElementById('footerLikeCount').textContent = data.likes;
    updateLikeUI();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function updateLikeUI() {
  document.querySelectorAll('.btn-like').forEach(btn => btn.classList.toggle('liked', liked));
}

// ── Share ─────────────────────────────────────────────────────
function copyLink() {
  navigator.clipboard.writeText(window.location.href).then(() => showToast('Link copied!', 'success'));
}

function shareTwitter() {
  const text = encodeURIComponent(`"${POST_TITLE}" — `);
  const url  = encodeURIComponent(window.location.href);
  window.open(`https://twitter.com/intent/tweet?text=${text}&url=${url}`, '_blank', 'noopener,width=550,height=400');
}

// ── Comments ──────────────────────────────────────────────────
async function loadComments() {
  try {
    const r = await fetch(`/api/blog/posts/${POST_ID}/comments`);
    const comments = await r.json();
    renderComments(comments);
  } catch {}
}

function renderComments(comments) {
  const list  = document.getElementById('commentsList');
  const empty = document.getElementById('commentsEmpty');
  if (!comments.length) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  list.innerHTML = comments.map(c => `
    <div class="comment-item" id="comment-${c.id}">
      <img class="comment-avatar" src="${esc(c.avatar)}" alt="">
      <div class="comment-bubble">
        <div class="comment-header">
          <span class="comment-author">${esc(c.display_name)}</span>
          <span class="comment-date">${fmtDate(c.created_at)}</span>
          ${(USER_ID && (c.user_id == USER_ID || /* post owner */ false))
            ? `<button class="comment-delete" onclick="deleteComment(${c.id})">Delete</button>`
            : ''}
        </div>
        <div class="comment-text">${esc(c.content)}</div>
      </div>
    </div>`).join('');
}

async function submitComment() {
  const content = document.getElementById('commentContent').value.trim();
  if (!content) return;
  const authorName = document.getElementById('commentName').value.trim();
  try {
    const r = await fetch(`/api/blog/posts/${POST_ID}/comments`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, author_name: authorName || 'Anonymous' })
    });
    const c = await r.json();
    if (!r.ok) throw new Error(c.error);
    document.getElementById('commentContent').value = '';
    document.getElementById('commentName').value    = '';
    document.getElementById('commentsEmpty').classList.add('hidden');
    document.getElementById('commentsList').insertAdjacentHTML('afterbegin', `
      <div class="comment-item" id="comment-${c.id}">
        <img class="comment-avatar" src="${esc(c.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(c.display_name)}&size=40&background=6366f1&color=fff`)}" alt="">
        <div class="comment-bubble">
          <div class="comment-header">
            <span class="comment-author">${esc(c.display_name)}</span>
            <span class="comment-date">Just now</span>
            <button class="comment-delete" onclick="deleteComment(${c.id})">Delete</button>
          </div>
          <div class="comment-text">${esc(c.content)}</div>
        </div>
      </div>`);
    showToast('Comment posted!', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function deleteComment(id) {
  if (!confirm('Delete this comment?')) return;
  try {
    await fetch(`/api/blog/comments/${id}`, { method: 'DELETE', credentials: 'include' });
    document.getElementById(`comment-${id}`)?.remove();
    showToast('Deleted', 'success');
  } catch {}
}

// ── Utilities ─────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (type ? ' ' + type : '');
  t.classList.remove('hidden');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add('hidden'), 2800);
}
