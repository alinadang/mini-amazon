from flask import Blueprint, request, jsonify, current_app, render_template, flash, redirect, url_for, g, abort
from flask_login import login_required, current_user
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

    # page number
    try:
        page = int(page_raw) if page_raw is not None else 1
    except Exception:
        page = 1

    sort_key = request.args.get('sort', 'price')
    if sort_key not in ('price', 'name', 'id', 'rating', 'sales'):
        sort_key = 'price'

    sort_dir = request.args.get('dir', None)
    sort_dir = (sort_dir or '').lower()
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'asc'

    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    ratings = request.args.getlist('ratings') or []

    min_price_raw = request.args.get('min_price', '').strip()
    max_price_raw = request.args.get('max_price', '').strip()

    def _parse_price(p):
        if p is None or p == '':
            return None
        try:
            v = float(p)
            if v < 0:
                return None
            return v
        except Exception:
            return None

    min_price_val = _parse_price(min_price_raw)
    max_price_val = _parse_price(max_price_raw)

    current_app.logger.debug(
        f"product_browser: page={page} per_page={per_page} sort={sort_key} dir={sort_dir} q='{q}' "
        f"category='{category}' ratings='{ratings}' min_price='{min_price_val}' max_price='{max_price_val}'"
    )

    try:
        categories = Product.get_categories()
        category_filter = category if category else None

        products, total = Product.get_page(
            page=page,
            per_page=per_page,
            sort=sort_key,
            direction=sort_dir,
            q=q if q else None,
            category=category_filter,
            available=True,
            ratings=ratings,
            min_price=min_price_val,
            max_price=max_price_val
        )

        total_pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1

        # Defensive: ensure avg_rating set (Product.get_page should do this)
        pids = [p.id for p in products]
        if pids:
            rows = current_app.db.execute("""
                SELECT product_id, AVG(rating)::numeric AS avg_rating
                FROM Reviews
                WHERE product_id = ANY(:pids)
                GROUP BY product_id
            """, pids=pids)
            avg_map = {r[0]: float(r[1]) for r in rows} if rows else {}
            for p in products:
                if getattr(p, 'avg_rating', None) is None:
                    p.avg_rating = avg_map.get(p.id)
                else:
                    try:
                        p.avg_rating = float(p.avg_rating) if p.avg_rating is not None else None
                    except Exception:
                        p.avg_rating = avg_map.get(p.id)
        else:
            for p in products:
                p.avg_rating = None

        try:
            ui_max_price = Product.get_max_price()
        except Exception:
            current_app.logger.exception("Could not compute max price")
            ui_max_price = 0.0

        return render_template(
            'product_browser.html',
            products=products,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            sort=sort_key,
            dir=sort_dir,
            k=per_page,
            q=q,
            category=category,
            categories=categories,
            error=None,
            ratings_selected=ratings or [],
            min_price=(min_price_raw if min_price_raw != '' else ''),
            max_price=(max_price_raw if max_price_raw != '' else ''),
            ui_max_price=ui_max_price
        )
    except Exception as e:
        current_app.logger.exception("Error in product_browser")
        return render_template(
            'product_browser.html',
            products=[],
            page=page,
            per_page=per_page,
            total=0,
            total_pages=0,
            sort=sort_key,
            dir=sort_dir,
            k=per_page,
            q=q,
            category=category,
            categories=Product.get_categories(),
            error=str(e),
            ratings_selected=ratings or [],
            min_price=(min_price_raw if min_price_raw != '' else ''),
            max_price=(max_price_raw if max_price_raw != '' else ''),
            ui_max_price=Product.get_max_price() if hasattr(Product, 'get_max_price') else 0
        )


@bp.route('/product/<int:pid>')
def product_detail(pid):
    product = Product.get(pid)
    if not product:
        abort(404)

    db = current_app.db

    avg_row = db.execute("SELECT AVG(rating)::numeric FROM Reviews WHERE product_id = :pid", pid=pid)
    product.avg_rating = float(avg_row[0][0]) if avg_row and avg_row[0][0] is not None else None

    product_total_sold = 0
    try:
        total_row = db.execute("SELECT COALESCE(SUM(quantity),0) FROM OrderItems WHERE product_id = :pid", pid=pid)
        if total_row:
            product_total_sold = int(total_row[0][0])
    except Exception:
        current_app.logger.exception("Could not fetch product total sales; continuing with zero")

    creator = None
    if getattr(product, 'creator_id', None) is not None:
        r = db.execute("SELECT id, firstname, lastname FROM Users WHERE id = :uid", uid=product.creator_id)
        if r:
            creator = {'id': r[0][0], 'firstname': r[0][1], 'lastname': r[0][2]}

    sellers_rows = db.execute("""
      SELECT i.seller_id, i.quantity, COALESCE(i.seller_price, p.price) as seller_price,
             u.firstname, u.lastname
      FROM Inventory i
      JOIN Users u ON u.id = i.seller_id
      LEFT JOIN Products p ON p.id = i.product_id
      WHERE i.product_id = :pid
      ORDER BY i.seller_id
    """, pid=pid)

    sellers = []
    if sellers_rows:
        for r in sellers_rows:
            sellers.append({
                'seller_id': r[0],
                'quantity': r[1],
                'seller_price': float(r[2]) if r[2] is not None else None,
                'firstname': r[3],
                'lastname': r[4]
            })

    review_rows = db.execute("""
      SELECT r.rating, r.comment, r.date_reviewed, u.firstname, u.lastname
      FROM Reviews r
      LEFT JOIN Users u ON u.id = r.user_id
      WHERE r.product_id = :pid
      ORDER BY r.date_reviewed DESC
    """, pid=pid)

    reviews = []
    if review_rows:
        for r in review_rows:
            reviews.append({
                'rating': int(r[0]),
                'comment': r[1],
                'date_reviewed': r[2],
                'firstname': r[3],
                'lastname': r[4]
            })

    return render_template(
        'product_detail.html',
        product=product,
        sellers=sellers,
        reviews=reviews,
        creator=creator,
        product_total_sold=product_total_sold
    )


@bp.route('/product/<int:pid>/sell', methods=['POST'])
@login_required
def product_sell(pid):
    db = current_app.db

    prod = Product.get(pid)
    if not prod:
        flash("Product not found", "danger")
        return redirect(url_for('products_api.product_browser'))

    qty_raw = request.form.get('qty') or request.form.get('quantity') or '0'
    try:
        qty = int(qty_raw)
        if qty <= 0:
            raise ValueError()
    except Exception:
        flash("Quantity must be a positive integer", "danger")
        return redirect(url_for('products_api.product_detail', pid=pid))

    seller_price = None
    price_raw = (request.form.get('seller_price') or '').strip()
    if price_raw != '':
        try:
            seller_price = float(price_raw)
            if seller_price < 0:
                raise ValueError()
        except Exception:
            flash("Seller price must be a non-negative number", "danger")
            return redirect(url_for('products_api.product_detail', pid=pid))

    seller_id = current_user.id

    try:
        if seller_price is not None:
            db.execute("""
                INSERT INTO Inventory (seller_id, product_id, quantity, seller_price)
                VALUES (:seller_id, :pid, :qty, :seller_price)
                ON CONFLICT (seller_id, product_id) DO UPDATE
                  SET quantity = Inventory.quantity + EXCLUDED.quantity,
                      seller_price = EXCLUDED.seller_price;
            """, seller_id=seller_id, pid=pid, qty=qty, seller_price=seller_price)
        else:
            update_res = db.execute("""
                UPDATE Inventory
                SET quantity = quantity + :qty
                WHERE seller_id = :seller_id AND product_id = :pid
                RETURNING seller_id;
            """, qty=qty, seller_id=seller_id, pid=pid)
            if not update_res:
                db.execute("""
                    INSERT INTO Inventory (seller_id, product_id, quantity, seller_price)
                    VALUES (:seller_id, :pid, :qty, NULL)
                """, seller_id=seller_id, pid=pid, qty=qty)
        flash("Your inventory has been updated", "success")
    except Exception:
        current_app.logger.exception("Error adding/updating inventory")
        flash("Could not update inventory", "danger")

    return redirect(url_for('products_api.product_detail', pid=pid))

@bp.route('/product/new', methods=['GET', 'POST'])
@login_required
def product_new():
    db = current_app.db
    categories = Product.get_categories()

    if request.method == 'GET':
        return render_template('product_form.html', product=None, categories=categories, action='Create')

    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()
    image_url = (request.form.get('image_url') or '').strip()
    price_raw = request.form.get('price')
    category_name = (request.form.get('category') or '').strip()

    if not name:
        flash('Name is required', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Create')
    try:
        price = float(price_raw)
        if price < 0:
            raise ValueError()
    except Exception:
        flash('Price must be a non-negative number', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Create')

    category_id = None
    if category_name:
        row = db.execute("SELECT id FROM Categories WHERE name = :name", name=category_name)
        if row:
            category_id = row[0][0]

    try:
        res = db.execute("""
            INSERT INTO Products (name, description, image_url, price, available, category_id, creator_id)
            VALUES (:name, :description, :image_url, :price, :available, :category_id, :creator_id)
            RETURNING id
        """, name=name, description=description or None, image_url=image_url or None,
           price=price, available=True, category_id=category_id, creator_id=current_user.id)
        new_id = res[0][0]
        flash('Product created', 'success')
        return redirect(url_for('products_api.product_detail', pid=new_id))
    except Exception as e:
        current_app.logger.exception("Error creating product")
        flash(f'Could not create product: {str(e)}', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Create')


@bp.route('/product/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def product_edit(pid):
    db = current_app.db
    product = Product.get(pid)
    if not product:
        abort(404)

    if product.creator_id is not None and product.creator_id != current_user.id:
        flash('Not authorized to edit this product', 'danger')
        return redirect(url_for('products_api.product_detail', pid=pid))

    categories = Product.get_categories()

    if request.method == 'GET':
        return render_template('product_form.html', product=product, categories=categories, action='Edit')

    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()
    image_url = (request.form.get('image_url') or '').strip()
    price_raw = request.form.get('price')
    category_name = (request.form.get('category') or '').strip()

    if not name:
        flash('Name is required', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Edit')
    try:
        price = float(price_raw)
        if price < 0:
            raise ValueError()
    except Exception:
        flash('Price must be a non-negative number', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Edit')

    category_id = None
    if category_name:
        row = db.execute("SELECT id FROM Categories WHERE name = :name", name=category_name)
        if row:
            category_id = row[0][0]

    try:
        db.execute("""
            UPDATE Products
            SET name = :name,
                description = :description,
                image_url = :image_url,
                price = :price,
                category_id = :category_id
            WHERE id = :pid
        """, name=name, description=description or None, image_url=image_url or None,
           price=price, category_id=category_id, pid=pid)
        flash('Product updated', 'success')
        return redirect(url_for('products_api.product_detail', pid=pid))
    except Exception as e:
        current_app.logger.exception("Error updating product")
        flash(f'Could not update product: {str(e)}', 'danger')
        return render_template('product_form.html', product=request.form, categories=categories, action='Edit')