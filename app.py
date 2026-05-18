from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import mysql.connector
import bcrypt
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import jwt
import datetime
from functools import wraps
from dotenv import load_dotenv
import json
import re

load_dotenv()

#app = Flask(__name__)
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get('SECRET_KEY', 'c043b7fa0d6a6c011a47a5915a2ed6bfff8f597934b3753742436ff5c523581f')
CORS(app, supports_credentials=True)

# ─── OAuth Setup ───────────────────────────────────────────────────────────────
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# ─── Database ──────────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'linkvault'),
        password=os.environ.get('DB_PASS', ''),
        database=os.environ.get('DB_NAME', 'linkvault'),
        charset='utf8mb4'
    )

# ─── JWT Auth ──────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get('JWT_SECRET', '6bd2dcc10ec19c88dff460f81f03330c8158e3af3723cd2f3fb7dcc24675cdf4')

def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated

def optional_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
        request.user_id = verify_token(token)
        return f(*args, **kwargs)
    return decorated

# ─── Pages ─────────────────────────────────────────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.svg'), 200, {'Content-Type': 'image/svg+xml'}

@app.route('/')
def index():
    return redirect('/explore')

@app.route('/dashboard')
def dashboard():
    token = request.cookies.get('token')
    if not verify_token(token):
        return redirect('/explore')
    return render_template('dashboard.html')

@app.route('/explore')
def explore():
    return render_template('explore.html')

# ─── Auth Routes ───────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT id FROM users WHERE email=%s', (email,))
        if cur.fetchone():
            return jsonify({'error': 'Email already registered'}), 400
        cur.execute(
            'INSERT INTO users (name, email, password_hash, avatar) VALUES (%s,%s,%s,%s)',
            (name, email, hashed, f"https://ui-avatars.com/api/?name={name.replace(' ','+')}&background=6366f1&color=fff")
        )
        db.commit()
        user_id = cur.lastrowid
        token = create_token(user_id)
        resp = jsonify({'success': True, 'user': {'id': user_id, 'name': name, 'email': email}})
        resp.set_cookie('token', token, httponly=True, samesite='Lax', max_age=30*24*3600)
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT * FROM users WHERE email=%s', (email,))
        user = cur.fetchone()
        if not user or not user['password_hash']:
            return jsonify({'error': 'Invalid credentials'}), 401
        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return jsonify({'error': 'Invalid credentials'}), 401
        token = create_token(user['id'])
        resp = jsonify({'success': True, 'user': {'id': user['id'], 'name': user['name'], 'email': user['email'], 'avatar': user['avatar']}})
        resp.set_cookie('token', token, httponly=True, samesite='Lax', max_age=30*24*3600)
        return resp
    finally:
        db.close()

@app.route('/api/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/api/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        userinfo = token.get('userinfo')
        email = userinfo['email']
        name = userinfo.get('name', email)
        avatar = userinfo.get('picture', '')
        google_id = userinfo['sub']

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE google_id=%s OR email=%s', (google_id, email))
        user = cur.fetchone()
        if not user:
            cur.execute(
                'INSERT INTO users (name, email, avatar, google_id) VALUES (%s,%s,%s,%s)',
                (name, email, avatar, google_id)
            )
            db.commit()
            user_id = cur.lastrowid
        else:
            user_id = user['id']
            if not user['google_id']:
                cur.execute('UPDATE users SET google_id=%s, avatar=%s WHERE id=%s', (google_id, avatar, user_id))
                db.commit()
        db.close()
        jwt_token = create_token(user_id)
        resp = redirect('/dashboard')
        resp.set_cookie('token', jwt_token, httponly=True, samesite='Lax', max_age=30*24*3600)
        return resp
    except Exception as e:
        return redirect(f'/?error={str(e)}')

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({'success': True})
    resp.delete_cookie('token')
    return resp

@app.route('/api/auth/me')
@login_required
def me():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute('SELECT id, name, email, avatar, bio, created_at FROM users WHERE id=%s', (request.user_id,))
    user = cur.fetchone()
    db.close()
    if user and user.get('created_at'):
        user['created_at'] = user['created_at'].isoformat()
    return jsonify(user)

# ─── URL Metadata ──────────────────────────────────────────────────────────────
@app.route('/api/fetch-meta', methods=['POST'])
@login_required
def fetch_meta():
    url = request.json.get('url', '')
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; LinkVault/1.0)'}
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
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
    except Exception as e:
        parsed = urlparse(url)
        return jsonify({'title': '', 'description': '', 'image': '', 'favicon': f"https://www.google.com/s2/favicons?domain={parsed.netloc}&sz=64", 'url': url})

# ─── Links CRUD ────────────────────────────────────────────────────────────────
@app.route('/api/links', methods=['GET'])
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

@app.route('/api/links', methods=['POST'])
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

@app.route('/api/links/<int:link_id>', methods=['PUT'])
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

@app.route('/api/links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('DELETE FROM links WHERE id=%s AND user_id=%s', (link_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/links/<int:link_id>/visit', methods=['POST'])
@login_required
def visit_link(link_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('UPDATE links SET visit_count=visit_count+1, last_visited=NOW() WHERE id=%s AND user_id=%s', (link_id, request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ─── Collections ───────────────────────────────────────────────────────────────
@app.route('/api/collections', methods=['GET'])
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

@app.route('/api/collections', methods=['POST'])
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

@app.route('/api/collections/<int:col_id>', methods=['DELETE'])
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
@app.route('/api/tags', methods=['GET'])
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
@app.route('/api/stats', methods=['GET'])
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

# ─── Explore (public links) ────────────────────────────────────────────────────
@app.route('/api/explore', methods=['GET'])
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

@app.route('/api/explore/trending-tags', methods=['GET'])
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

# ─── Profile update ────────────────────────────────────────────────────────────
@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute('UPDATE users SET name=%s, bio=%s WHERE id=%s',
        (data.get('name','')[:100], data.get('bio','')[:300], request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
