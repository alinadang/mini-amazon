from flask import Flask, request, jsonify, redirect, url_for
from flask_login import LoginManager
from .config import Config
from .db import DB

login = LoginManager()
login.login_view = 'users.login'

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.db = DB(app)
    login.init_app(app)

    from .index import bp as index_bp
    app.register_blueprint(index_bp)

    from .users import bp as user_bp
    app.register_blueprint(user_bp)

    from .wishlist import bp as wishlist_bp
    app.register_blueprint(wishlist_bp)

    from .products import bp as products_bp
    app.register_blueprint(products_bp)

    from .sellers import sellers_bp
    app.register_blueprint(sellers_bp)

    from .cart import cart_bp
    app.register_blueprint(cart_bp)

    from .social import social_bp
    app.register_blueprint(social_bp)

    # --- Begin new code ---

    @login.unauthorized_handler
    def unauthorized_callback():
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        return redirect(url_for('users.login'))

    # --- End new code ---

    return app
