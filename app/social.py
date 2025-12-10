from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    redirect,
    url_for,
)
from flask_login import login_required, current_user


social_bp = Blueprint("social", __name__)


@social_bp.route("/reviews", methods=["GET"])
def reviews_page():
    """
    Renders the 'Latest Reviews' page.

    Optional query param:
      ?user_id=0  → show that user's 5 most recent reviews
    """
    db = current_app.db

    user_id = request.args.get("user_id", type=int)
    items = []
    error = None

    if user_id is not None:
        query = """
            SELECT r.product_id, r.rating, r.comment, r.date_reviewed
            FROM Reviews r
            WHERE r.user_id = :input_user_id
            ORDER BY r.date_reviewed DESC
            LIMIT 5
        """
        try:
            rows = db.execute(query, input_user_id=user_id)
            columns = ["product_id", "rating", "comment", "date_reviewed"]
            items = [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            current_app.logger.exception("DB error fetching reviews")
            error = "Error fetching reviews from the database."

    # This matches the variables used in reviews.html
    return render_template("reviews.html", user_id=user_id, items=items, error=error)


@social_bp.route("/api/feedback", methods=["GET"])
def get_feedback():
    """
    JSON API: return the 5 most recent reviews for a given user_id.

    Called via: GET /api/feedback?user_id=...
    """
    input_user_id = request.args.get("user_id", type=int)
    if input_user_id is None:
        return jsonify({"error": "user_id required"}), 400

    db = current_app.db

    query = """
        SELECT r.product_id, r.rating, r.comment, r.date_reviewed
        FROM Reviews r
        WHERE r.user_id = :input_user_id
        ORDER BY r.date_reviewed DESC
        LIMIT 5
    """
    try:
        reviews = db.execute(query, input_user_id=input_user_id)
    except Exception as e:
        current_app.logger.exception("DB error fetching reviews (API)")
        return jsonify({"error": "database_error", "detail": str(e)}), 500

    columns = ["product_id", "rating", "comment", "date_reviewed"]
    return jsonify([dict(zip(columns, row)) for row in reviews])


@social_bp.route("/submit_review", methods=["POST"])
def submit_review():
    db = current_app.db

    user_id_raw = request.form.get("user_id")
    product_id_raw = request.form.get("product_id")
    rating_raw = request.form.get("rating")
    comment = (request.form.get("comment") or "").strip()

    if not (user_id_raw and product_id_raw and rating_raw and comment):
        return jsonify(
            {"error": "user_id, product_id, rating, and comment are required"}
        ), 400

    try:
        user_id = int(user_id_raw)
        product_id = int(product_id_raw)
        rating = int(rating_raw)
    except ValueError:
        return jsonify({"error": "user_id, product_id, and rating must be integers"}), 400

    if rating < 1 or rating > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400

    insert_sql = """
        INSERT INTO Reviews (user_id, product_id, rating, comment, date_reviewed)
        VALUES (:uid, :pid, :rating, :comment, CURRENT_TIMESTAMP)
    """

    db.execute(
        insert_sql,
        uid=user_id,
        pid=product_id,
        rating=rating,
        comment=comment,
    )

    return redirect(url_for("social.reviews_page", user_id=user_id))

@social_bp.route("/my_reviews", methods=["GET"])
@login_required
def my_reviews():
    """
    List all reviews authored by the current user,
    sorted newest-first.
    """
    db = current_app.db

    rows = db.execute("""
        SELECT r.review_id,
               r.product_id,
               r.rating,
               r.comment,
               r.date_reviewed,
               p.name
        FROM Reviews r
        JOIN Products p ON p.id = r.product_id
        WHERE r.user_id = :uid
        ORDER BY r.date_reviewed DESC
    """, uid=current_user.id)

    items = [
        {
            "review_id": row[0],
            "product_id": row[1],
            "rating": int(row[2]),
            "comment": row[3],
            "date_reviewed": row[4],
            "product_name": row[5],
        }
        for row in (rows or [])
    ]

    return render_template("my_reviews.html", items=items)


@social_bp.route("/review_summary")
def review_summary():
    """
    Show summary ratings for products and sellers:
    - average rating
    - number of ratings
    - lists sorted by rating or date
    """
    db = current_app.db

    # sort param: "rating" (default) or "date"
    sort = request.args.get("sort", "rating")
    if sort not in ("rating", "date"):
        sort = "rating"

    # ----- Products summary -----
    # Only show products that have at least 1 review
    if sort == "rating":
        prod_order = "AVG(r.rating) DESC, COUNT(*) DESC"
    else:
        prod_order = "MAX(r.date_reviewed) DESC"

    product_rows = db.execute(f"""
        SELECT p.id,
               p.name,
               AVG(r.rating)::numeric AS avg_rating,
               COUNT(*) AS num_reviews,
               MAX(r.date_reviewed) AS last_reviewed
        FROM Reviews r
        JOIN Products p ON p.id = r.product_id
        GROUP BY p.id, p.name
        ORDER BY {prod_order}
    """)

    product_summaries = []
    for row in product_rows or []:
        product_summaries.append({
            "product_id":   row[0],
            "product_name": row[1],
            "avg_rating":   float(row[2]) if row[2] is not None else None,
            "num_reviews":  int(row[3]),
            "last_reviewed": row[4],
        })

    # ----- Sellers summary -----
    # Only show sellers that have at least 1 SellerReview
    if sort == "rating":
        seller_order = "AVG(sr.rating) DESC, COUNT(*) DESC"
    else:
        seller_order = "MAX(sr.date_reviewed) DESC"

    seller_rows = db.execute(f"""
        SELECT u.id,
               u.firstname,
               u.lastname,
               AVG(sr.rating)::numeric AS avg_rating,
               COUNT(*) AS num_reviews,
               MAX(sr.date_reviewed) AS last_reviewed
        FROM SellerReviews sr
        JOIN Users u ON u.id = sr.seller_id
        GROUP BY u.id, u.firstname, u.lastname
        ORDER BY {seller_order}
    """)

    seller_summaries = []
    for row in seller_rows or []:
        seller_summaries.append({
            "seller_id":    row[0],
            "seller_name":  f"{row[1]} {row[2]}",
            "avg_rating":   float(row[3]) if row[3] is not None else None,
            "num_reviews":  int(row[4]),
            "last_reviewed": row[5],
        })

    return render_template(
        "review_summary.html",
        sort=sort,
        product_summaries=product_summaries,
        seller_summaries=seller_summaries,
    )




