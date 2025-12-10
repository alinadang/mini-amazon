from flask import (
    Blueprint, current_app, render_template,
    request, redirect, url_for, flash, abort
)
from flask_login import login_required, current_user

reviews_bp = Blueprint("reviews", __name__)


# ------------- helper: has this user ever bought from this seller? -------------
def _user_has_bought_from_seller(db, buyer_id, seller_id):
    rows = db.execute("""
        SELECT 1
        FROM Orders o
        JOIN OrderItems oi ON oi.order_id = o.id
        WHERE o.user_id = :buyer
          AND oi.seller_id = :seller
        LIMIT 1
    """, buyer=buyer_id, seller=seller_id)
    return bool(rows)


# ------------- 1. "My Reviews" page (product + seller reviews) -------------
@reviews_bp.route('/my_reviews')
@login_required
def my_reviews():
    db = current_app.db

    # product reviews by this user
    product_rows = db.execute("""
        SELECT r.review_id,
               r.product_id,
               p.name,
               r.rating,
               r.comment,
               r.date_reviewed
        FROM Reviews r
        JOIN Products p ON p.id = r.product_id
        WHERE r.user_id = :uid
        ORDER BY r.date_reviewed DESC
    """, uid=current_user.id)

    product_reviews = []
    for r in product_rows or []:
        product_reviews.append({
            'review_id':   r[0],
            'product_id':  r[1],
            'product_name': r[2],
            'rating':      int(r[3]),
            'comment':     r[4],
            'date_reviewed': r[5],
        })

    # seller reviews by this user
    seller_rows = db.execute("""
        SELECT sr.id,
               sr.seller_id,
               u.firstname,
               u.lastname,
               sr.rating,
               sr.comment,
               sr.date_reviewed
        FROM SellerReviews sr
        JOIN Users u ON u.id = sr.seller_id
        WHERE sr.user_id = :uid
        ORDER BY sr.date_reviewed DESC
    """, uid=current_user.id)

    seller_reviews = []
    for r in seller_rows or []:
        seller_reviews.append({
            'id':           r[0],
            'seller_id':    r[1],
            'seller_name':  f"{r[2]} {r[3]}",
            'rating':       int(r[4]),
            'comment':      r[5],
            'date_reviewed': r[6],
        })

    return render_template(
        'my_reviews.html',
        product_reviews=product_reviews,
        seller_reviews=seller_reviews
    )


# ------------- 2. Create / edit a seller review -------------
@reviews_bp.route('/seller/<int:seller_id>/review', methods=['GET', 'POST'])
@login_required
def seller_review(seller_id):
    db = current_app.db

    # fetch seller info
    seller_rows = db.execute("""
        SELECT id, firstname, lastname
        FROM Users
        WHERE id = :sid
    """, sid=seller_id)
    if not seller_rows:
        abort(404)

    seller = {
        'id':        seller_rows[0][0],
        'firstname': seller_rows[0][1],
        'lastname':  seller_rows[0][2],
    }

    # enforce "must have ordered from this seller"
    if not _user_has_bought_from_seller(db, current_user.id, seller_id):
        flash("You can only review sellers you have purchased from.", "warning")
        # adjust this redirect to wherever makes sense (e.g., your orders page)
        return redirect(url_for('users.account')) if 'users.account' in current_app.view_functions else redirect('/')

    # Check if this user already has a seller review for this seller
    row = db.execute("""
        SELECT id, rating, comment
        FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)
    existing = row[0] if row else None  # (id, rating, comment)

    if request.method == 'GET':
        return render_template(
            'seller_review_form.html',
            seller=seller,
            existing=existing
        )

    # POST: save (insert or update)
    rating_raw = request.form.get('rating')
    comment = (request.form.get('comment') or '').strip()

    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except Exception:
        flash("Rating must be an integer between 1 and 5.", "danger")
        return render_template(
            'seller_review_form.html',
            seller=seller,
            existing=existing
        )

    try:
        if existing:
            db.execute("""
                UPDATE SellerReviews
                SET rating = :rating,
                    comment = :comment,
                    date_reviewed = NOW()
                WHERE id = :rid AND user_id = :uid
            """, rating=rating,
               comment=comment or None,
               rid=existing[0],
               uid=current_user.id)
            flash("Seller review updated.", "success")
        else:
            db.execute("""
                INSERT INTO SellerReviews (seller_id, user_id, rating, comment, date_reviewed)
                VALUES (:sid, :uid, :rating, :comment, NOW())
            """, sid=seller_id,
               uid=current_user.id,
               rating=rating,
               comment=comment or None)
            flash("Seller review added.", "success")

        # adjust this to whatever your "seller profile" route is
        return redirect(url_for('reviews.seller_reviews_list', seller_id=seller_id))

    except Exception as e:
        current_app.logger.exception("Error saving seller review")
        flash(f"Could not save seller review: {e}", "danger")
        return render_template(
            'seller_review_form.html',
            seller=seller,
            existing=existing
        )


# ------------- 3. Delete seller review -------------
@reviews_bp.route('/seller/<int:seller_id>/review/delete', methods=['POST'])
@login_required
def seller_review_delete(seller_id):
    db = current_app.db

    db.execute("""
        DELETE FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)

    flash("Seller review removed.", "success")
    return redirect(url_for('reviews.my_reviews'))
    # or redirect to seller page if you prefer


# ------------- 4. Public list of reviews for a seller -------------
@reviews_bp.route('/seller/<int:seller_id>/reviews')
def seller_reviews_list(seller_id):
    db = current_app.db

    seller_rows = db.execute("""
        SELECT id, firstname, lastname
        FROM Users
        WHERE id = :sid
    """, sid=seller_id)
    if not seller_rows:
        abort(404)

    seller = {
        'id':        seller_rows[0][0],
        'firstname': seller_rows[0][1],
        'lastname':  seller_rows[0][2],
    }

    rows = db.execute("""
        SELECT sr.rating, sr.comment, sr.date_reviewed,
               u.firstname, u.lastname
        FROM SellerReviews sr
        JOIN Users u ON u.id = sr.user_id
        WHERE sr.seller_id = :sid
        ORDER BY sr.date_reviewed DESC
    """, sid=seller_id)

    reviews = []
    for r in rows or []:
        reviews.append({
            'rating':       int(r[0]),
            'comment':      r[1],
            'date_reviewed': r[2],
            'reviewer_name': f"{r[3]} {r[4]}",
        })

    return render_template(
        'seller_reviews_list.html',
        seller=seller,
        reviews=reviews
    )
