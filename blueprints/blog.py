from flask import Blueprint, request, jsonify, render_template, redirect, abort, Response
import json, re, unicodedata, os, datetime
from utils import get_db, login_required, optional_auth, verify_token

bp = Blueprint('blog', __name__)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _generate_slug(title):
    s = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    s = re.sub(r'[-\s]+', '-', s)
    return (s or 'post')[:180]


def _unique_slug(cur, base, exclude_id=None):
    slug, i = base, 2
    while True:
        if exclude_id:
            cur.execute('SELECT id FROM blog_posts WHERE slug=%s AND id!=%s', (slug, exclude_id))
        else:
            cur.execute('SELECT id FROM blog_posts WHERE slug=%s', (slug,))
        if not cur.fetchone():
            return slug
        slug, i = f'{base}-{i}', i + 1


def _reading_time(content_json):
    try:
        data = json.loads(content_json) if isinstance(content_json, str) else content_json
        text = ''
        for b in data.get('blocks', []):
            bd, bt = b.get('data', {}), b.get('type', '')
            if bt in ('paragraph', 'header', 'quote'):
                text += ' ' + re.sub(r'<[^>]+>', '', bd.get('text', ''))
            elif bt == 'list':
                text += ' '.join(bd.get('items', []))
            elif bt == 'code':
                text += ' ' + bd.get('code', '')
        return max(1, round(len(text.split()) / 200))
    except Exception:
        return 1


def _to_html(content_json):
    import html as _e
    try:
        data = json.loads(content_json) if isinstance(content_json, str) else content_json
    except Exception:
        return '<p>Content unavailable.</p>'

    parts = []
    for b in data.get('blocks', []):
        bt, bd = b.get('type', ''), b.get('data', {})

        if bt == 'paragraph':
            parts.append(f'<p>{bd.get("text","")}</p>')

        elif bt == 'header':
            lvl = min(max(int(bd.get('level', 2)), 1), 6)
            text = bd.get('text', '')
            anchor = re.sub(r'[-\s]+', '-', re.sub(r'[^\w\s-]', '', re.sub(r'<[^>]+>', '', text)).strip().lower()).strip('-')
            parts.append(f'<h{lvl} id="{_e.escape(anchor)}">{text}</h{lvl}>')

        elif bt == 'list':
            tag = 'ol' if bd.get('style') == 'ordered' else 'ul'
            items = ''.join(f'<li>{i}</li>' for i in bd.get('items', []))
            parts.append(f'<{tag}>{items}</{tag}>')

        elif bt == 'checklist':
            rows = ''
            for item in bd.get('items', []):
                chk = 'checked' if item.get('checked') else ''
                rows += f'<label class="cl-item"><input type="checkbox" {chk} disabled><span>{item.get("text","")}</span></label>'
            parts.append(f'<div class="blog-checklist">{rows}</div>')

        elif bt == 'quote':
            cap = f'<cite>{bd["caption"]}</cite>' if bd.get('caption') else ''
            align = _e.escape(bd.get('alignment', 'left'))
            parts.append(f'<blockquote style="text-align:{align}"><p>{bd.get("text","")}</p>{cap}</blockquote>')

        elif bt == 'code':
            lang = _e.escape(bd.get('language', ''))
            code = _e.escape(bd.get('code', ''))
            parts.append(f'<pre><code class="language-{lang}">{code}</code></pre>')

        elif bt == 'image':
            url = _e.escape(bd.get('file', {}).get('url', '') or bd.get('url', ''))
            cap = bd.get('caption', '')
            cls = ' '.join(filter(None, [
                'stretched'  if bd.get('stretched')       else '',
                'bordered'   if bd.get('withBorder')      else '',
                'with-bg'    if bd.get('withBackground')  else '',
            ]))
            cap_html = f'<figcaption>{cap}</figcaption>' if cap else ''
            parts.append(f'<figure class="blog-figure {cls}"><img src="{url}" alt="{_e.escape(cap)}" loading="lazy">{cap_html}</figure>')

        elif bt == 'embed':
            embed = _e.escape(bd.get('embed', ''))
            cap = bd.get('caption', '')
            cap_html = f'<figcaption>{cap}</figcaption>' if cap else ''
            parts.append(f'<figure class="blog-embed"><iframe src="{embed}" frameborder="0" allowfullscreen loading="lazy"></iframe>{cap_html}</figure>')

        elif bt == 'table':
            rows_html = ''
            for i, row in enumerate(bd.get('content', [])):
                tag = 'th' if i == 0 else 'td'
                rows_html += '<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in row) + '</tr>'
            parts.append(f'<div class="table-wrap"><table>{rows_html}</table></div>')

        elif bt == 'delimiter':
            parts.append('<div class="blog-delimiter">✦ &nbsp; ✦ &nbsp; ✦</div>')

        elif bt == 'warning':
            parts.append(f'<div class="blog-warning"><strong>{bd.get("title","")}</strong><p>{bd.get("message","")}</p></div>')

    return '\n'.join(parts)


def _fmt_date(dt):
    if not dt:
        return ''
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return f'{months[dt.month - 1]} {dt.day}, {dt.year}'


# ── Page routes ───────────────────────────────────────────────────────────────

@bp.route('/blog/<slug>')
@optional_auth
def post_page(slug):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT p.*, u.name as author_name, u.avatar as author_avatar, u.bio as author_bio
            FROM blog_posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.slug=%s AND (p.status='published' OR p.user_id=%s)
        ''', (slug, request.user_id or -1))
        post = cur.fetchone()
    finally:
        db.close()
    if not post:
        abort(404)
    db2 = get_db()
    cur2 = db2.cursor()
    cur2.execute('UPDATE blog_posts SET views=views+1 WHERE id=%s', (post['id'],))
    db2.commit()
    db2.close()

    post['content_html'] = _to_html(post.get('content') or '{}')
    post['pub_date']     = _fmt_date(post.get('published_at'))
    post['is_owner']     = (request.user_id == post['user_id'])
    post['tags_list']    = [t.strip() for t in (post.get('tags') or '').split(',') if t.strip()]
    return render_template('blog_post.html', post=post, user_id=request.user_id)


@bp.route('/write')
@bp.route('/write/<int:post_id>')
def editor_page(post_id=None):
    user_id = verify_token(request.cookies.get('token'))
    if not user_id:
        return redirect('/explore')
    post = None
    if post_id:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM blog_posts WHERE id=%s AND user_id=%s', (post_id, user_id))
        post = cur.fetchone()
        db.close()
        if not post:
            abort(404)
    return render_template('blog_editor.html', post=post)


# ── API ───────────────────────────────────────────────────────────────────────

@bp.route('/api/blog/posts', methods=['GET'])
@optional_auth
def list_posts():
    q        = request.args.get('q', '')
    tag      = request.args.get('tag', '')
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(int(request.args.get('per_page', 12)), 50)
    offset   = (page - 1) * per_page

    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        conds, params = ["p.status='published'"], []
        if q:
            conds.append('(MATCH(p.title,p.excerpt,p.tags) AGAINST(%s IN BOOLEAN MODE) OR p.title LIKE %s)')
            params += [f'{q}*', f'%{q}%']
        if tag:
            conds.append('FIND_IN_SET(%s, p.tags)')
            params.append(tag)

        where = ' AND '.join(conds)
        cur.execute(f'SELECT COUNT(*) as total FROM blog_posts p WHERE {where}', params)
        total = cur.fetchone()['total']

        cur.execute(f'''
            SELECT p.id, p.title, p.slug, p.excerpt, p.cover_image, p.tags,
                   p.reading_time, p.views, p.likes, p.published_at, p.featured,
                   u.name as author_name, u.avatar as author_avatar
            FROM blog_posts p JOIN users u ON p.user_id=u.id
            WHERE {where}
            ORDER BY p.featured DESC, p.published_at DESC
            LIMIT %s OFFSET %s
        ''', params + [per_page, offset])
        posts = cur.fetchall()
    finally:
        db.close()

    for p in posts:
        if p.get('published_at'):
            p['pub_date']    = _fmt_date(p['published_at'])
            p['published_at'] = p['published_at'].isoformat()

    return jsonify({'posts': posts, 'total': total, 'page': page, 'per_page': per_page})


@bp.route('/api/blog/posts', methods=['POST'])
@login_required
def create_post():
    data    = request.json or {}
    title   = (data.get('title') or 'Untitled').strip()[:500]
    content = data.get('content', '{}')
    try:
        content = json.dumps(json.loads(content) if isinstance(content, str) else content)
    except Exception:
        content = '{}'

    excerpt = (data.get('excerpt') or '').strip()[:500]
    cover   = (data.get('cover_image') or '')[:500]
    tags    = (data.get('tags') or '')[:300]
    rtime   = _reading_time(content)

    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        slug = _unique_slug(cur, _generate_slug(title))
        cur.execute('''
            INSERT INTO blog_posts (user_id,title,slug,excerpt,content,cover_image,tags,reading_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (request.user_id, title, slug, excerpt, content, cover, tags, rtime))
        db.commit()
        post_id = cur.lastrowid
        cur.execute('SELECT id,title,slug,status FROM blog_posts WHERE id=%s', (post_id,))
        return jsonify(cur.fetchone()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/blog/posts/<int:post_id>', methods=['GET'])
@optional_auth
def get_post(post_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT p.*, u.name as author_name, u.avatar as author_avatar
            FROM blog_posts p JOIN users u ON p.user_id=u.id
            WHERE p.id=%s AND (p.status='published' OR p.user_id=%s)
        ''', (post_id, request.user_id or -1))
        post = cur.fetchone()
    finally:
        db.close()
    if not post:
        return jsonify({'error': 'Not found'}), 404
    for f in ('created_at', 'updated_at', 'published_at'):
        if post.get(f): post[f] = post[f].isoformat()
    return jsonify(post)


@bp.route('/api/blog/posts/<int:post_id>', methods=['PUT'])
@login_required
def update_post(post_id):
    data = request.json or {}
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT id,slug FROM blog_posts WHERE id=%s AND user_id=%s', (post_id, request.user_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        title   = (data.get('title') or 'Untitled').strip()[:500]
        content = data.get('content', '{}')
        try:
            content = json.dumps(json.loads(content) if isinstance(content, str) else content)
        except Exception:
            content = '{}'

        excerpt = (data.get('excerpt') or '').strip()[:500]
        cover   = (data.get('cover_image') or '')[:500]
        tags    = (data.get('tags') or '')[:300]
        rtime   = _reading_time(content)
        raw_slug = (data.get('slug') or _generate_slug(title)).strip()
        slug    = _unique_slug(cur, raw_slug, exclude_id=post_id)

        cur.execute('''
            UPDATE blog_posts SET title=%s,slug=%s,excerpt=%s,content=%s,
            cover_image=%s,tags=%s,reading_time=%s,updated_at=NOW()
            WHERE id=%s AND user_id=%s
        ''', (title, slug, excerpt, content, cover, tags, rtime, post_id, request.user_id))
        db.commit()
        return jsonify({'success': True, 'slug': slug})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/blog/posts/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM blog_posts WHERE id=%s AND user_id=%s', (post_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})


@bp.route('/api/blog/posts/<int:post_id>/publish', methods=['POST'])
@login_required
def toggle_publish(post_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT id,status FROM blog_posts WHERE id=%s AND user_id=%s', (post_id, request.user_id))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        new_status = 'published' if row['status'] == 'draft' else 'draft'
        if new_status == 'published':
            cur.execute("UPDATE blog_posts SET status='published',published_at=NOW() WHERE id=%s", (post_id,))
        else:
            cur.execute("UPDATE blog_posts SET status='draft' WHERE id=%s", (post_id,))
        db.commit()
        return jsonify({'success': True, 'status': new_status})
    finally:
        db.close()


@bp.route('/api/blog/posts/<int:post_id>/like', methods=['POST'])
@optional_auth
def like_post(post_id):
    data = request.json or {}
    session_key = (data.get('session_key') or '')[:64]

    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        if request.user_id:
            cur.execute('SELECT id FROM blog_likes WHERE post_id=%s AND user_id=%s', (post_id, request.user_id))
            if cur.fetchone():
                cur.execute('DELETE FROM blog_likes WHERE post_id=%s AND user_id=%s', (post_id, request.user_id))
                cur.execute('UPDATE blog_posts SET likes=GREATEST(0,likes-1) WHERE id=%s', (post_id,))
                action = 'unliked'
            else:
                cur.execute('INSERT INTO blog_likes (post_id,user_id) VALUES (%s,%s)', (post_id, request.user_id))
                cur.execute('UPDATE blog_posts SET likes=likes+1 WHERE id=%s', (post_id,))
                action = 'liked'
        elif session_key:
            cur.execute('SELECT id FROM blog_likes WHERE post_id=%s AND session_key=%s', (post_id, session_key))
            if cur.fetchone():
                cur.execute('DELETE FROM blog_likes WHERE post_id=%s AND session_key=%s', (post_id, session_key))
                cur.execute('UPDATE blog_posts SET likes=GREATEST(0,likes-1) WHERE id=%s', (post_id,))
                action = 'unliked'
            else:
                cur.execute('INSERT INTO blog_likes (post_id,session_key) VALUES (%s,%s)', (post_id, session_key))
                cur.execute('UPDATE blog_posts SET likes=likes+1 WHERE id=%s', (post_id,))
                action = 'liked'
        else:
            return jsonify({'error': 'No identity'}), 400

        db.commit()
        cur.execute('SELECT likes FROM blog_posts WHERE id=%s', (post_id,))
        return jsonify({'success': True, 'action': action, 'likes': cur.fetchone()['likes']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/blog/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT c.id, c.content, c.author_name, c.created_at,
                   u.name as user_name, u.avatar as user_avatar
            FROM blog_comments c
            LEFT JOIN users u ON c.user_id=u.id
            WHERE c.post_id=%s ORDER BY c.created_at ASC LIMIT 200
        ''', (post_id,))
        comments = cur.fetchall()
    finally:
        db.close()

    for c in comments:
        if c.get('created_at'): c['created_at'] = c['created_at'].isoformat()
        c['display_name'] = c.get('user_name') or c.get('author_name') or 'Anonymous'
        c['avatar'] = c.get('user_avatar') or \
            f"https://ui-avatars.com/api/?name={c['display_name'][:1]}&size=40&background=6366f1&color=fff"
    return jsonify(comments)


@bp.route('/api/blog/posts/<int:post_id>/comments', methods=['POST'])
@optional_auth
def add_comment(post_id):
    data    = request.json or {}
    content = (data.get('content') or '').strip()[:2000]
    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    author_name = (data.get('author_name') or 'Anonymous').strip()[:100]

    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM blog_posts WHERE id=%s AND status='published'", (post_id,))
        if not cur.fetchone():
            return jsonify({'error': 'Post not found'}), 404
        cur.execute(
            'INSERT INTO blog_comments (post_id,user_id,author_name,content) VALUES (%s,%s,%s,%s)',
            (post_id, request.user_id, None if request.user_id else author_name, content)
        )
        db.commit()
        cid = cur.lastrowid
        if request.user_id:
            cur.execute('''
                SELECT c.id, c.content, c.created_at, u.name as user_name, u.avatar as user_avatar
                FROM blog_comments c JOIN users u ON c.user_id=u.id WHERE c.id=%s
            ''', (cid,))
        else:
            cur.execute('SELECT id,content,author_name,created_at FROM blog_comments WHERE id=%s', (cid,))
        c = cur.fetchone()
        if c.get('created_at'): c['created_at'] = c['created_at'].isoformat()
        c['display_name'] = c.get('user_name') or c.get('author_name') or 'Anonymous'
        return jsonify(c), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/blog/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        DELETE c FROM blog_comments c
        LEFT JOIN blog_posts p ON c.post_id=p.id
        WHERE c.id=%s AND (c.user_id=%s OR p.user_id=%s)
    ''', (comment_id, request.user_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})


@bp.route('/api/blog/my-posts', methods=['GET'])
@login_required
def my_posts():
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT id,title,slug,status,tags,reading_time,views,likes,
                   cover_image,excerpt,created_at,updated_at,published_at
            FROM blog_posts WHERE user_id=%s ORDER BY updated_at DESC
        ''', (request.user_id,))
        posts = cur.fetchall()
    finally:
        db.close()
    for p in posts:
        for f in ('created_at', 'updated_at', 'published_at'):
            if p.get(f): p[f] = p[f].isoformat()
    return jsonify(posts)


@bp.route('/api/blog/tags', methods=['GET'])
def blog_tags():
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT tags FROM blog_posts WHERE status='published' AND tags!=''")
        rows = cur.fetchall()
    finally:
        db.close()
    counts = {}
    for row in rows:
        for t in row['tags'].split(','):
            t = t.strip()
            if t: counts[t] = counts.get(t, 0) + 1
    return jsonify([{'name': k, 'count': v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:20]])


@bp.route('/api/blog/upload', methods=['POST'])
@login_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': 0, 'message': 'No file'}), 400
    f = request.files['image']
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'success': 0, 'message': 'Invalid file type'}), 400
    import uuid
    fname = f'{uuid.uuid4().hex}{ext}'
    path  = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'blog', fname)
    f.save(path)
    return jsonify({'success': 1, 'file': {'url': f'/static/uploads/blog/{fname}'}})


@bp.route('/api/blog/rss.xml', methods=['GET'])
def rss_feed():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT p.title, p.slug, p.excerpt, p.published_at, u.name as author_name
        FROM blog_posts p JOIN users u ON p.user_id=u.id
        WHERE p.status='published' ORDER BY p.published_at DESC LIMIT 20
    ''')
    posts = cur.fetchall()
    db.close()
    host = request.host_url.rstrip('/')
    items = ''
    for p in posts:
        dt = p['published_at'].strftime('%a, %d %b %Y %H:%M:%S +0000') if p.get('published_at') else ''
        items += f'''
        <item>
          <title><![CDATA[{p["title"]}]]></title>
          <link>{host}/blog/{p["slug"]}</link>
          <description><![CDATA[{p.get("excerpt","") or ""}]]></description>
          <author>{p["author_name"]}</author>
          <pubDate>{dt}</pubDate>
          <guid>{host}/blog/{p["slug"]}</guid>
        </item>'''
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>LinkVault Blog</title>
    <link>{host}/explore</link>
    <description>Stories and articles from the LinkVault community</description>
    {items}
  </channel>
</rss>'''
    return Response(xml, mimetype='application/rss+xml')
