from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    redirect,
    url_for,
)

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
