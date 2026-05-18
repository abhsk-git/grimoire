from flask import Flask, render_template, request, redirect
from flask_cors import CORS
from dotenv import load_dotenv
import os

_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, 'config', '.env'))

from extensions import oauth
from utils import verify_token


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY', 'c043b7fa0d6a6c011a47a5915a2ed6bfff8f597934b3753742436ff5c523581f')
    CORS(app, supports_credentials=True)

    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    from blueprints.auth import bp as auth_bp
    from blueprints.links import bp as links_bp
    from blueprints.explore import bp as explore_bp
    from blueprints.blog import bp as blog_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(blog_bp)

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

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
