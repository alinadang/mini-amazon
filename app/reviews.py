from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

reviews_bp = Blueprint("reviews", __name__)

# ----------------------------------------------
# Helper: has user purchased from seller?
# ----------------------------------------------
def _user_has_bought_from_seller(db, buyer_id, seller_id):
    row = db.execute("""
        SELECT 1
        FROM Orders o
        JOIN OrderItems oi ON oi.order_id = o.id
        WHERE o.user_id = :buyer AND oi.seller_id = :seller
        LIMIT 1
    """, buyer=buyer_id, seller=seller_id)
    return bool(row)


# ----------------------------------------------
# 1. My Reviews (product reviews + seller reviews)
# ----------------------------------------------
@reviews_bp.route('/my_reviews')
@login_required
def my_reviews():
    db = current_app.db
    reviews = []

    # PRODUCT REVIEWS
    prod_rows = db.execute("""
        SELECT r.review_id,
               p.id,
               p.name,
               r.rating,
               r.comment,
               r.date_reviewed
        FROM Reviews r
        JOIN Products p ON p.id = r.product_id
        WHERE r.user_id = :uid
    """, uid=current_user.id)

    for r in prod_rows:
        reviews.append({
            "kind": "product",
            "rating": r[3],
            "comment": r[4],
            "date_reviewed": r[5],
            "product_id": r[1],
            "product_name": r[2],
            "seller_id": None,
            "seller_name": None
        })

    # SELLER REVIEWS
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
    """, uid=current_user.id)

    for r in seller_rows:
        reviews.append({
            "kind": "seller",
            "rating": r[4],
            "comment": r[5],
            "date_reviewed": r[6],
            "product_id": None,
            "product_name": None,
            "seller_id": r[1],
            "seller_name": f"{r[2]} {r[3]}"
        })

    # Sort combined list (newest first)
    reviews.sort(key=lambda r: r["date_reviewed"], reverse=True)

    return render_template("my_reviews.html", reviews=reviews)


# ----------------------------------------------
# 2. Create / Edit Seller Review
# ----------------------------------------------
@reviews_bp.route('/seller/<int:seller_id>/review', methods=['GET', 'POST'])
@login_required
def seller_review(seller_id):
    db = current_app.db

    # seller info
    row = db.execute("""
        SELECT id, firstname, lastname
        FROM Users
        WHERE id = :sid
    """, sid=seller_id)

    if not row:
        abort(404)

    seller = {
        "id": row[0][0],
        "firstname": row[0][1],
        "lastname": row[0][2]
    }

    # ensure user has purchased from this seller
    if not _user_has_bought_from_seller(db, current_user.id, seller_id):
        flash("You can only review sellers you have purchased from.", "warning")
        return redirect('/')

    # check for existing review
    existing_row = db.execute("""
        SELECT id, rating, comment
        FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)

    existing = existing_row[0] if existing_row else None

    if request.method == 'GET':
        return render_template("seller_review_form.html",
                               seller=seller,
                               existing=existing)

    # POST: save review
    rating = int(request.form["rating"])
    comment = request.form.get("comment") or None

    if existing:
        db.execute("""
            UPDATE SellerReviews
            SET rating = :rating, comment = :comment, date_reviewed = NOW()
            WHERE id = :rid
        """, rating=rating, comment=comment, rid=existing[0])
    else:
        db.execute("""
            INSERT INTO SellerReviews (seller_id, user_id, rating, comment, date_reviewed)
            VALUES (:sid, :uid, :rating, :comment, NOW())
        """, sid=seller_id, uid=current_user.id, rating=rating, comment=comment)

    flash("Review saved.", "success")
    return redirect(url_for("reviews.my_reviews"))


# ----------------------------------------------
# 3. Delete Seller Review
# ----------------------------------------------
@reviews_bp.route('/seller/<int:seller_id>/review/delete', methods=['POST'])
@login_required
def delete_seller_review(seller_id):
    db = current_app.db
    db.execute("""
        DELETE FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)

    flash("Review deleted.", "success")
    return redirect(url_for("reviews.my_reviews"))
