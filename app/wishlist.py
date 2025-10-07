from flask import Blueprint, jsonify, redirect, url_for
from flask_login import current_user, login_required
from app.models.wishlist import WishlistItem

bp = Blueprint('wishlist', __name__)

@bp.route('/wishlist')
@login_required
def wishlist():
    """Return the current user's wishlist as JSON."""
    if not current_user.is_authenticated:
        return jsonify({}), 404
    items = WishlistItem.get_all_by_uid(current_user.id)
    return jsonify([item.__dict__ for item in items])
