from flask import Blueprint, request, jsonify
import requests as http_requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from utils import get_db, login_required

bp = Blueprint('links', __name__)


# ─── URL Metadata ──────────────────────────────────────────────────────────────
@bp.route('/api/fetch-meta', methods=['POST'])
@login_required
def fetch_meta():
    url = request.json.get('url', '')
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; Grimoire/1.0)'}
        r = http_requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        soup = BeautifulSoup(r.text, 'html.parser')

        title = ''
        for sel in ['meta[property="og:title"]', 'meta[name="twitter:title"]', 'title']:
            el = soup.select_one(sel)
            if el:
                title = el.get('content') or el.get_text()
                if title: break

        desc = ''
        for sel in ['meta[property="og:description"]', 'meta[name="description"]', 'meta[name="twitter:description"]']:
            el = soup.select_one(sel)
            if el:
                desc = el.get('content', '')
                if desc: break

        image = ''
        for sel in ['meta[property="og:image"]', 'meta[name="twitter:image"]']:
            el = soup.select_one(sel)
            if el:
                image = el.get('content', '')
                if image: break

        parsed = urlparse(url)
        favicon = f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=64"

        return jsonify({'title': title.strip()[:255], 'description': desc.strip()[:500], 'image': image, 'favicon': favicon, 'url': r.url})
    except Exception:
        parsed = urlparse(url)
        return jsonify({'title': '', 'description': '', 'image': '', 'favicon': f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=64", 'url': url})


# ─── Links CRUD ────────────────────────────────────────────────────────────────
@bp.route('/api/links', methods=['GET'])
@login_required
def get_links():
    q = request.args.get('q', '')
    tag = request.args.get('tag', '')
    collection = request.args.get('collection', '')
    is_public = request.args.get('public', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page

    db = get_db()
    cur = db.cursor(dictionary=True)
    conditions = ['l.user_id = %s']
    params = [request.user_id]

    if q:
        conditions.append('(MATCH(l.title, l.description, l.tags) AGAINST(%s IN BOOLEAN MODE) OR l.url LIKE %s OR l.title LIKE %s)')
        params += [f'{q}*', f'%{q}%', f'%{q}%']
    if tag:
        conditions.append('FIND_IN_SET(%s, l.tags)')
        params.append(tag)
    if collection:
        conditions.append('l.collection_id = %s')
        params.append(collection)
    if is_public == '1':
        conditions.append('l.is_public = 1')
    elif is_public == '0':
        conditions.append('l.is_public = 0')

    where = ' AND '.join(conditions)
    cur.execute(f'SELECT COUNT(*) as total FROM links l WHERE {where}', params)
    total = cur.fetchone()['total']

    cur.execute(f'''
        SELECT l.*, c.name as collection_name, c.color as collection_color
        FROM links l
        LEFT JOIN collections c ON l.collection_id = c.id
        WHERE {where}
        ORDER BY l.created_at DESC
        LIMIT %s OFFSET %s
    ''', params + [per_page, offset])
    links = cur.fetchall()
    db.close()

    for l in links:
        if l.get('created_at'): l['created_at'] = l['created_at'].isoformat()
        if l.get('updated_at'): l['updated_at'] = l['updated_at'].isoformat()

    return jsonify({'links': links, 'total': total, 'page': page, 'per_page': per_page})


@bp.route('/api/links', methods=['POST'])
@login_required
def create_link():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    if not url.startswith('http'):
        url = 'https://' + url

    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            INSERT INTO links (user_id, url, title, description, image, favicon, tags, collection_id, is_public, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            request.user_id, url,
            data.get('title', '')[:255],
            data.get('description', '')[:500],
            data.get('image', '')[:500],
            data.get('favicon', '')[:255],
            data.get('tags', '')[:255],
            data.get('collection_id') or None,
            1 if data.get('is_public') else 0,
            data.get('notes', '')[:2000]
        ))
        db.commit()
        link_id = cur.lastrowid
        cur.execute('SELECT * FROM links WHERE id=%s', (link_id,))
        link = cur.fetchone()
        if link.get('created_at'): link['created_at'] = link['created_at'].isoformat()
        return jsonify(link), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/links/<int:link_id>', methods=['PUT'])
@login_required
def update_link(link_id):
    data = request.json
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT id FROM links WHERE id=%s AND user_id=%s', (link_id, request.user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Not found'}), 404
        cur.execute('''
            UPDATE links SET title=%s, description=%s, tags=%s, collection_id=%s,
            is_public=%s, notes=%s, image=%s, updated_at=NOW()
            WHERE id=%s AND user_id=%s
        ''', (
            data.get('title', '')[:255], data.get('description', '')[:500],
            data.get('tags', '')[:255], data.get('collection_id') or None,
            1 if data.get('is_public') else 0,
            data.get('notes', '')[:2000], data.get('image', '')[:500],
            link_id, request.user_id
        ))
        db.commit()
        return jsonify({'success': True})
    finally:
        db.close()


@bp.route('/api/links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM links WHERE id=%s AND user_id=%s', (link_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})


@bp.route('/api/links/<int:link_id>/visit', methods=['POST'])
@login_required
def visit_link(link_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('UPDATE links SET visit_count=visit_count+1, last_visited=NOW() WHERE id=%s AND user_id=%s', (link_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})


# ─── Collections ───────────────────────────────────────────────────────────────
@bp.route('/api/collections', methods=['GET'])
@login_required
def get_collections():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT c.*, COUNT(l.id) as link_count
        FROM collections c
        LEFT JOIN links l ON c.id = l.collection_id
        WHERE c.user_id = %s
        GROUP BY c.id
        ORDER BY c.name
    ''', (request.user_id,))
    cols = cur.fetchall()
    db.close()
    return jsonify(cols)


@bp.route('/api/collections', methods=['POST'])
@login_required
def create_collection():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('INSERT INTO collections (user_id, name, color, icon) VALUES (%s,%s,%s,%s)',
        (request.user_id, name[:100], data.get('color', '#6366f1'), data.get('icon', '📁')))
    db.commit()
    col_id = cur.lastrowid
    cur.execute('SELECT * FROM collections WHERE id=%s', (col_id,))
    col = cur.fetchone()
    db.close()
    return jsonify(col), 201


@bp.route('/api/collections/<int:col_id>', methods=['DELETE'])
@login_required
def delete_collection(col_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('UPDATE links SET collection_id=NULL WHERE collection_id=%s AND user_id=%s', (col_id, request.user_id))
    cur.execute('DELETE FROM collections WHERE id=%s AND user_id=%s', (col_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})


# ─── Tags ──────────────────────────────────────────────────────────────────────
@bp.route('/api/tags', methods=['GET'])
@login_required
def get_tags():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('SELECT tags FROM links WHERE user_id=%s AND tags != ""', (request.user_id,))
    rows = cur.fetchall()
    db.close()
    tag_counts = {}
    for row in rows:
        for tag in row['tags'].split(','):
            tag = tag.strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    tags = [{'name': k, 'count': v} for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])]
    return jsonify(tags)


# ─── Stats ─────────────────────────────────────────────────────────────────────
@bp.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('SELECT COUNT(*) as total, SUM(is_public) as public_count, SUM(visit_count) as total_visits FROM links WHERE user_id=%s', (request.user_id,))
    stats = cur.fetchone()
    cur.execute('SELECT COUNT(*) as cols FROM collections WHERE user_id=%s', (request.user_id,))
    stats['collections'] = cur.fetchone()['cols']
    cur.execute('SELECT title, url, favicon, visit_count FROM links WHERE user_id=%s ORDER BY visit_count DESC LIMIT 5', (request.user_id,))
    stats['top_links'] = cur.fetchall()
    db.close()
    for k in ['total', 'public_count', 'total_visits', 'collections']:
        stats[k] = stats[k] or 0
    return jsonify(stats)
