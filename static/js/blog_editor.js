// ── Blog Editor ───────────────────────────────────────────────
let editor = null;
let autosaveTimer = null;
let isSaving = false;
let currentPostId = POST_ID;
let currentStatus = POST_STATUS;

document.addEventListener('DOMContentLoaded', () => {
  initEditor();
  autoResizeTextarea(document.getElementById('postTitle'));

  // Ctrl/Cmd+S saves draft
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveDraft(); }
  });

  // Restore cover from settings input
  const savedCover = document.getElementById('coverUrlInput').value;
  if (savedCover) applyCoverUrl();
});

function initEditor() {
  const parsedData = (() => {
    try { return POST_DATA ? JSON.parse(POST_DATA) : null; } catch { return null; }
  })();

  editor = new EditorJS({
    holder: 'editorjs',
    autofocus: !parsedData,
    placeholder: 'Start writing your story… (press Tab for blocks)',
    data: parsedData || { blocks: [] },
    tools: {
      header:     { class: Header,     inlineToolbar: true, config: { levels: [1,2,3,4], defaultLevel: 2 } },
      list:       { class: List,       inlineToolbar: true, config: { defaultStyle: 'unordered' } },
      checklist:  { class: Checklist,  inlineToolbar: true },
      quote:      { class: Quote,      inlineToolbar: true },
      warning:    { class: Warning },
      code:       { class: CodeTool },
      delimiter:  { class: Delimiter },
      table:      { class: Table,      inlineToolbar: true },
      image:      {
        class: ImageTool,
        config: {
          uploader: {
            uploadByFile(file) {
              const fd = new FormData();
              fd.append('image', file);
              return fetch('/api/blog/upload', { method: 'POST', body: fd, credentials: 'include' })
                .then(r => r.json());
            },
            uploadByUrl(url) {
              return Promise.resolve({ success: 1, file: { url } });
            }
          }
        }
      },
      embed:      { class: Embed, config: { services: { youtube: true, vimeo: true, twitter: true, codepen: true } } },
      inlineCode: { class: InlineCode },
      marker:     { class: Marker },
      underline:  { class: Underline },
    },
    onChange: () => { scheduleAutosave(); updateStats(); },
    onReady: () => { injectImageTips(); }
  });
}

function injectImageTips() {
  // no-op: tips handled via topbar upload button
}

// ── Topbar image upload ───────────────────────────────────────
async function topbarUploadImage(input) {
  const file = input.files[0];
  if (!file) return;
  const label = input.closest('label');
  label.classList.add('uploading');
  label.childNodes[1].textContent = ' Uploading…';
  try {
    const fd = new FormData();
    fd.append('image', file);
    const r = await fetch('/api/blog/upload', { method: 'POST', body: fd, credentials: 'include' });
    const data = await r.json();
    if (!r.ok || !data.file?.url) throw new Error(data.error || 'Upload failed');
    await editor.blocks.insert('image', { file: { url: data.file.url }, caption: '', withBorder: false, stretched: false, withBackground: false });
    showToast('Image inserted!', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    label.classList.remove('uploading');
    label.childNodes[1].textContent = ' Upload Image';
    input.value = '';
  }
}

// ── Autosave ──────────────────────────────────────────────────
function scheduleAutosave() {
  clearTimeout(autosaveTimer);
  setStatus('Unsaved changes…', '');
  autosaveTimer = setTimeout(() => saveDraft(true), 4000);
}

async function saveDraft(silent = false) {
  if (isSaving) return;
  isSaving = true;
  setStatus('Saving…', 'saving');
  try {
    const data = await buildPayload();
    const method = currentPostId ? 'PUT' : 'POST';
    const url    = currentPostId ? `/api/blog/posts/${currentPostId}` : '/api/blog/posts';
    const r = await fetch(url, {
      method, credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const json = await r.json();
    if (!r.ok) throw new Error(json.error || 'Save failed');

    if (!currentPostId && json.id) {
      currentPostId = json.id;
      history.replaceState(null, '', `/write/${currentPostId}`);
    }
    if (json.slug) {
      const slugEl = document.getElementById('postSlug');
      if (slugEl && !slugEl.value) slugEl.value = json.slug;
    }
    setStatus('All changes saved', 'saved');
    if (!silent) showToast('Saved!', 'success');
  } catch (e) {
    setStatus('Save failed', 'error');
    if (!silent) showToast(e.message, 'error');
  } finally {
    isSaving = false;
  }
}

async function buildPayload() {
  const content = await editor.save();
  return {
    title:       document.getElementById('postTitle').value.trim() || 'Untitled',
    content:     JSON.stringify(content),
    excerpt:     document.getElementById('postExcerpt').value.trim(),
    tags:        document.getElementById('postTags').value.trim(),
    cover_image: document.getElementById('coverUrlInput').value.trim(),
    slug:        document.getElementById('postSlug').value.trim(),
  };
}

// ── Publish ───────────────────────────────────────────────────
async function togglePublish() {
  if (!currentPostId) {
    await saveDraft();
    if (!currentPostId) { showToast('Save the post first', 'error'); return; }
  }
  try {
    const r = await fetch(`/api/blog/posts/${currentPostId}/publish`, {
      method: 'POST', credentials: 'include'
    });
    const json = await r.json();
    if (!r.ok) throw new Error(json.error);
    currentStatus = json.status;
    updatePublishUI();
    showToast(json.status === 'published' ? 'Post published! 🎉' : 'Moved to drafts', 'success');
    if (json.status === 'published') {
      const slug = document.getElementById('postSlug').value;
      if (slug) {
        setTimeout(() => {
          if (confirm('Post is live! Open it now?')) window.open(`/blog/${slug}`, '_blank');
        }, 400);
      }
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function updatePublishUI() {
  const btn   = document.getElementById('publishBtn');
  const dot   = document.getElementById('statusDot');
  const txt   = document.getElementById('statusText');
  if (currentStatus === 'published') {
    btn.textContent = 'Unpublish';
    btn.classList.add('published');
    dot.className = 'settings-status-dot published';
    txt.textContent = 'Published';
  } else {
    btn.textContent = 'Publish';
    btn.classList.remove('published');
    dot.className = 'settings-status-dot draft';
    txt.textContent = 'Draft';
  }
}

// ── Delete ────────────────────────────────────────────────────
async function deletePost() {
  if (!currentPostId) return;
  if (!confirm('Delete this post permanently?')) return;
  try {
    const r = await fetch(`/api/blog/posts/${currentPostId}`, {
      method: 'DELETE', credentials: 'include'
    });
    if (r.ok) window.location.href = '/dashboard';
    else showToast('Delete failed', 'error');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Cover ─────────────────────────────────────────────────────
function openCoverModal() {
  if (document.getElementById('coverZone').classList.contains('has-cover')) return;
  document.getElementById('coverFileInput').click();
}

async function handleCoverFile(input) {
  const file = input.files[0];
  if (!file) return;
  const zone = document.getElementById('coverZone');
  zone.style.opacity = '0.5';
  try {
    const fd = new FormData();
    fd.append('image', file);
    const r = await fetch('/api/blog/upload', { method: 'POST', body: fd, credentials: 'include' });
    const data = await r.json();
    if (!r.ok || !data.file?.url) throw new Error(data.error || 'Upload failed');
    setCover(data.file.url);
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    zone.style.opacity = '';
    input.value = '';
  }
}

function setCover(url) {
  const zone = document.getElementById('coverZone');
  const img  = document.getElementById('coverPreviewImg');
  const ph   = document.getElementById('coverPlaceholder');
  img.src = url;
  img.style.display = 'block';
  ph.style.display  = 'none';
  zone.classList.add('has-cover');
  document.getElementById('coverUrlInput').value = url;
  const prev = document.getElementById('coverUrlPreview');
  if (prev) { prev.src = url; prev.classList.add('visible'); }
  scheduleAutosave();
}

function applyCoverUrl() {
  const url = document.getElementById('coverUrlInput').value.trim();
  if (url) setCover(url); else removeCover(null);
}

function previewCoverFromUrl(url) {
  const prev = document.getElementById('coverUrlPreview');
  if (prev) { prev.src = url || ''; url ? prev.classList.add('visible') : prev.classList.remove('visible'); }
}

function removeCover(e) {
  if (e) { e.preventDefault(); e.stopPropagation(); }
  document.getElementById('coverPreviewImg').style.display = 'none';
  document.getElementById('coverPlaceholder').style.display = 'flex';
  document.getElementById('coverZone').classList.remove('has-cover');
  document.getElementById('coverUrlInput').value = '';
  const prev = document.getElementById('coverUrlPreview');
  if (prev) { prev.src = ''; prev.classList.remove('visible'); }
  scheduleAutosave();
}

// ── Slug sync ─────────────────────────────────────────────────
function syncSlug() {
  const slugEl = document.getElementById('postSlug');
  if (slugEl.dataset.custom) return;
  const title = document.getElementById('postTitle').value;
  slugEl.value = title.toLowerCase().trim()
    .replace(/[^a-z0-9\s-]/g, '').replace(/[\s]+/g, '-').replace(/-+/g, '-').slice(0, 80);
}

// Mark slug as custom when user edits it manually
document.addEventListener('DOMContentLoaded', () => {
  const slugEl = document.getElementById('postSlug');
  if (slugEl) slugEl.addEventListener('input', () => { slugEl.dataset.custom = '1'; });
});

// ── Word count / reading time ─────────────────────────────────
async function updateStats() {
  try {
    const data = await editor.save();
    let text = '';
    for (const b of data.blocks) {
      const bd = b.data;
      if (['paragraph','header','quote'].includes(b.type)) text += ' ' + (bd.text || '').replace(/<[^>]+>/g, '');
      else if (b.type === 'list') text += ' ' + (bd.items || []).join(' ');
      else if (b.type === 'code') text += ' ' + (bd.code || '');
    }
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    const mins  = Math.max(1, Math.round(words / 200));
    document.getElementById('wordCountDisplay').textContent = `${words.toLocaleString()} word${words !== 1 ? 's' : ''}`;
    document.getElementById('readTimeDisplay').textContent  = `${mins} min read`;
  } catch {}
}

// ── Settings panel ────────────────────────────────────────────
function toggleSettings() {
  document.getElementById('settingsPanel').classList.toggle('open');
  document.getElementById('settingsOverlay').classList.toggle('open');
}

// ── Helpers ───────────────────────────────────────────────────
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

function setStatus(msg, cls) {
  const el = document.getElementById('saveStatus');
  el.textContent = msg;
  el.className = 'save-status' + (cls ? ' ' + cls : '');
}

function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (type ? ' ' + type : '');
  t.classList.remove('hidden');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add('hidden'), 2800);
}
