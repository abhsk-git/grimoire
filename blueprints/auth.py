from flask import Blueprint, request, jsonify, redirect, url_for
import bcrypt
from utils import get_db, create_token, verify_token, login_required
from extensions import oauth

bp = Blueprint('auth', __name__)


@bp.route('/api/auth/register', methods=['POST'])
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


@bp.route('/api/auth/login', methods=['POST'])
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


@bp.route('/api/auth/google')
def google_login():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route('/api/auth/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
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


@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({'success': True})
    resp.delete_cookie('token')
    return resp


@bp.route('/api/auth/me')
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


@bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.json
    db = get_db()
    cur = db.cursor()
    cur.execute('UPDATE users SET name=%s, bio=%s WHERE id=%s',
        (data.get('name', '')[:100], data.get('bio', '')[:300], request.user_id))
    db.commit()
    db.close()
    return jsonify({'success': True})
