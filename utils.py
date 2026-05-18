from flask import request, jsonify
import mysql.connector
import os
import jwt
import datetime
from functools import wraps


def get_db():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'linkvault'),
        password=os.environ.get('DB_PASS', ''),
        database=os.environ.get('DB_NAME', 'linkvault'),
        charset='utf8mb4'
    )


def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, os.environ.get('JWT_SECRET', ''), algorithm='HS256')


def verify_token(token):
    try:
        payload = jwt.decode(token, os.environ.get('JWT_SECRET', ''), algorithms=['HS256'])
        return payload['user_id']
    except Exception:
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
