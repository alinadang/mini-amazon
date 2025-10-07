from flask import Blueprint, redirect, url_for, render_template
from flask_login import current_user, login_required
import datetime
from humanize import naturaltime

from app.models.wishlist import WishlistItem

bp = Blueprint('wishlist', __name__)

def humanize_time(dt):
    return naturaltime(datetime.datetime.now() - dt)

@bp.route('/wishlist')
@login_required
def wishlist():
    items = WishlistItem.get_all_by_uid(current_user.id)
    return render_template(
        'wishlist.html',
        items=items,
        humanize_time=humanize_time
    )

@bp.route('/wishlist/add/<int:product_id>', methods=['POST'])
@login_required
def wishlist_add(product_id):
   WishlistItem.add(current_user.id, product_id)
   return redirect(url_for('wishlist.wishlist'))