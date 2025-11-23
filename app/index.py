from flask import render_template, current_app
from flask_login import current_user
from sqlalchemy import text

from .models.product import Product
from flask import Blueprint

bp = Blueprint('index', __name__)

@bp.route('/')
def index():
    products = Product.get_all(True)[:5]
    if current_user.is_authenticated:
        try:
            orders = current_app.db.execute(
                """
                SELECT o.id as order_id, p.name as product_name, oi.price, o.order_date
                FROM Orders o
                JOIN OrderItems oi ON o.id = oi.order_id
                JOIN Products p ON oi.product_id = p.id
                WHERE o.user_id = :uid
                ORDER BY o.order_date DESC
                LIMIT 10
                """,
                uid = current_user.id
            )
            purchase_history = [dict(zip(['order_id', 'product_name', 'price', 'order_date'], row)) for row in orders]
        except Exception as e:
            print("Error fetching purchases:", e)
            purchase_history = []
    else:
        purchase_history = None
    return render_template('index.html',
                          avail_products=products,
                          purchase_history=purchase_history)