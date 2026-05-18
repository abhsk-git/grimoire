from flask import Blueprint, request, jsonify
from utils import get_db, optional_auth

bp = Blueprint('explore', __name__)


@bp.route('/api/explore', methods=['GET'])
@optional_auth
def explore_links():
    q = request.args.get('q', '')
    tag = request.args.get('tag', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 24))
    offset = (page - 1) * per_page

    db = get_db()
    cur = db.cursor(dictionary=True)
    conditions = ['l.is_public = 1']
    params = []

    if q:
        conditions.append('(MATCH(l.title, l.description, l.tags) AGAINST(%s IN BOOLEAN MODE) OR l.title LIKE %s)')
        params += [f'{q}*', f'%{q}%']
    if tag:
        conditions.append('FIND_IN_SET(%s, l.tags)')
        params.append(tag)

    where = ' AND '.join(conditions)
    cur.execute(f'SELECT COUNT(*) as total FROM links l WHERE {where}', params)
    total = cur.fetchone()['total']

    cur.execute(f'''
        SELECT l.id, l.url, l.title, l.description, l.image, l.favicon, l.tags, l.visit_count, l.created_at,
               u.name as author_name, u.avatar as author_avatar
        FROM links l
        JOIN users u ON l.user_id = u.id
        WHERE {where}
        ORDER BY l.created_at DESC
        LIMIT %s OFFSET %s
    ''', params + [per_page, offset])
    links = cur.fetchall()
    db.close()

    for l in links:
        if l.get('created_at'): l['created_at'] = l['created_at'].isoformat()

    return jsonify({'links': links, 'total': total, 'page': page, 'per_page': per_page})


@bp.route('/api/explore/trending-tags', methods=['GET'])
def trending_tags():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('SELECT tags FROM links WHERE is_public=1 AND tags != ""')
    rows = cur.fetchall()
    db.close()
    tag_counts = {}
    for row in rows:
        for tag in row['tags'].split(','):
            tag = tag.strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:20]
    return jsonify([{'name': t[0], 'count': t[1]} for t in tags])
