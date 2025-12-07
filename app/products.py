# app/products.py
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

    # determine per_page 
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

    # sorting
    sort_key = request.args.get('sort', 'price')
    sort_dir = request.args.get('dir', '').lower()
    if sort_key not in ('price', 'name', 'id'):
        sort_key = 'price'
    if sort_dir not in ('asc', 'desc', ''):
        sort_dir = ''

    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    current_app.logger.debug(f"product_browser: page={page} per_page={per_page} sort={sort_key} dir={sort_dir} q='{q}' category='{category}'")

    try:
        categories = Product.get_categories()
        category_filter = category if category else None

        products, total = Product.get_page(page=page, per_page=per_page,
                                          sort=sort_key, direction=sort_dir or 'desc',
                                          q=q if q else None,
                                          category=category_filter,
                                          available=True)
        total_pages = max(1, math.ceil(total / per_page)) if per_page > 0 else 1

        # Grab avg ratings for products on this page in one query to avoid N+1
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
                p.avg_rating = avg_map.get(p.id)
        else:
            for p in products:
                p.avg_rating = None

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
                               category=category,
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
                               category=category,
                               categories=Product.get_categories(),
                               error=str(e))


@bp.route('/product/<int:pid>')
def product_detail(pid):
    product = Product.get(pid)
    if not product:
        abort(404)

    db = current_app.db

    # set avg_rating for the product
    avg_row = db.execute("SELECT AVG(rating)::numeric FROM Reviews WHERE product_id = :pid", pid=pid)
    product.avg_rating = float(avg_row[0][0]) if avg_row and avg_row[0][0] is not None else None

    # fetch creator info
    creator = None
    if getattr(product, 'creator_id', None) is not None:
        r = db.execute("SELECT id, firstname, lastname FROM Users WHERE id = :uid", uid=product.creator_id)
        if r:
            creator = {'id': r[0][0], 'firstname': r[0][1], 'lastname': r[0][2]}

    # fetch sellers and the seller's name
    sellers_rows = db.execute("""
      SELECT i.seller_id, i.quantity, COALESCE(i.seller_price, p.price) as seller_price,
             u.firstname, u.lastname
      FROM Inventory i
      JOIN Users u ON u.id = i.seller_id
      LEFT JOIN Products p ON p.id = i.product_id
      WHERE i.product_id = :pid AND i.quantity > 0
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

    # fetch reviews with user names
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

    return render_template('product_detail.html', product=product, sellers=sellers, reviews=reviews, creator=creator)

@bp.route('/product/<int:pid>/sell', methods=['POST'])
@login_required
def product_sell(pid):
    """
    Let the current user sell this product:
      - accepts form fields: qty or quantity (int) and seller_price (float, optional)
      - if Inventory row exists for (current_user.id, pid) update quantity and price,
        otherwise insert a new Inventory row.
    Redirects back to product detail page and flashes a message.
    """
    db = current_app.db

    # ensure product exists
    prod = Product.get(pid)
    if not prod:
        flash("Product not found", "danger")
        return redirect(url_for('products_api.product_browser'))

    # parse quantity (accept 'qty' or 'quantity')
    qty_raw = request.form.get('qty') or request.form.get('quantity') or '0'
    try:
        qty = int(qty_raw)
        if qty <= 0:
            raise ValueError()
    except Exception:
        flash("Quantity must be a positive integer", "danger")
        return redirect(url_for('products_api.product_detail', pid=pid))

    # parse price (optional)
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
        # Upsert inventory row: if exists, increment quantity and update price (if provided)
        if seller_price is not None:
            db.execute("""
                INSERT INTO Inventory (seller_id, product_id, quantity, seller_price)
                VALUES (:seller_id, :pid, :qty, :seller_price)
                ON CONFLICT (seller_id, product_id) DO UPDATE
                  SET quantity = Inventory.quantity + EXCLUDED.quantity,
                      seller_price = EXCLUDED.seller_price;
            """, seller_id=seller_id, pid=pid, qty=qty, seller_price=seller_price)
        else:
            # don't change seller_price if not provided; just increment quantity
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

    # only creator may edit 
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