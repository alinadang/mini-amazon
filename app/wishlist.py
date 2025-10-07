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

@bp.route('/wishlist/add/<int:product_id>', methods=['POST'])
@login_required
def wishlist_add(product_id):
   """Add a product to the current user's wishlist and redirect."""
   WishlistItem.add(current_user.id, product_id)
   return redirect(url_for('wishlist.wishlist'))