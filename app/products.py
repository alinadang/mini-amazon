from flask import Blueprint, request, jsonify, current_app, render_template
from .models.product import Product
import math

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
    page_raw = request.args.get('page', None)
    per_page_raw = request.args.get('per_page', None)
    k_raw = request.args.get('k', None)

    if per_page_raw is not None:
        try:
            per_page = int(per_page_raw)
        except Exception:
            per_page = 50
    elif k_raw is not None:
        try:
            per_page = int(k_raw)
        except Exception:
            per_page = 50
    else:
        per_page = 50
    
    if page_raw is not None:
        try:
            page = int(page_raw)
        except Exception:
            page = 1
    else:
        page = 1


    sort_key = request.args.get('sort', 'price')
    sort_dir = request.args.get('dir', '').lower()
    if sort_key not in ('price', 'name'):
        sort_key = 'price'
    if sort_dir not in ('asc', 'desc', ''):
        sort_dir = ''

    q = request.args.get('q', '').strip()

    try:
        products, total = Product.get_page(page=page, per_page=per_page,
                                          sort=sort_key, direction=sort_dir or 'desc',
                                          q=q if q else None,
                                          available=True)
        total_pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1

        # not used yet
        categories = []

        return render_template('product_browser.html',
                               products=products,
                               page=page,
                               per_page=per_page,
                               total=total,
                               total_pages=total_pages,
                               sort=sort_key,
                               dir=sort_dir,
                               k=per_page,
                               q=q,
                               category='',
                               categories=categories,
                               error=None)
    except Exception as e:
        current_app.logger.exception("Error in product_browser")
        return render_template('product_browser.html',
                               products=[],
                               page=page,
                               per_page=per_page,
                               total=0,
                               total_pages=0,
                               sort=sort_key,
                               dir=sort_dir,
                               k=per_page,
                               q=q,
                               category='',
                               categories=[],
                               error=str(e))