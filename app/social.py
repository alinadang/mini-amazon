from flask import Blueprint, request, jsonify, current_app, render_template

bp = Blueprint('social', __name__)

@bp.route('/reviews')
def reviews_page():
    """Renders the reviews frontend (reviews.html)."""
    return render_template('reviews.html')


@bp.route('/api/feedback', methods=['GET'])
def get_feedback():
    input_user_id = request.args.get('user_id')
    if not input_user_id:
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
        reviews = db.execute(query, {"input_user_id": int(input_user_id)})
    except Exception as e:
        current_app.logger.exception("DB error fetching reviews")
        return jsonify({"error": "database_error", "detail": str(e)}), 500

    columns = ['product_id', 'rating', 'comment', 'date_reviewed']
    return jsonify([dict(zip(columns, row)) for row in reviews])