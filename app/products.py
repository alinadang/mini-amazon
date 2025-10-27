from flask import Blueprint, request, jsonify, current_app, render_template
from .models.product import Product

bp = Blueprint('products_api', __name__, url_prefix='')

@bp.route('/api/products/top', methods=['GET'])
def top_products():
    k_raw = request.args.get('k', 10)
    try:
        k = int(k_raw)
        if k <= 0:
            k = 10
    except Exception:
        k = 10

    try:
        products = Product.get_top_k(k)
        data = []
        for p in products:
            price_val = float(p.price) if p.price is not None else None
            data.append({
                'id': p.id,
                'name': p.name,
                'price': price_val,
                'available': p.available
            })
        return jsonify(success=True, data=data)
    except Exception as e:
        current_app.logger.exception("Error fetching top products")
        return jsonify(success=False, error=str(e)), 500


@bp.route('/product_browser', methods=['GET'])
def product_browser():
    k_raw = request.args.get('k', 50)
    try:
        k = int(k_raw)
        if k <= 0 or k > 2000:
            k = 50
    except Exception:
        k = 50

    sort_key = request.args.get('sort', 'price')
    sort_dir = request.args.get('dir', '').lower()
    if sort_key not in ('price', 'name'):
        sort_key = 'price'
    if sort_dir not in ('asc', 'desc', ''):
        sort_dir = ''

    try:
        products = Product.get_all(True)

        if sort_key == 'price':
            reverse = (sort_dir != 'asc')
            products.sort(key=lambda p: (p.price or 0), reverse=reverse)
        else:
            reverse = (sort_dir == 'desc')
            products.sort(key=lambda p: (p.name or '').lower(), reverse=reverse)

        products = products[:k]

        return render_template('product_browser.html',
                               products=products,
                               k=k,
                               sort=sort_key,
                               dir=sort_dir,
                               error=None)
    except Exception as e:
        current_app.logger.exception("Error in product_browser")
        return render_template('product_browser.html',
                               products=[],
                               k=k,
                               sort=sort_key,
                               dir=sort_dir,
                               error=str(e))