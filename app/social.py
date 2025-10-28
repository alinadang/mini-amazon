from flask import Blueprint, request, jsonify, current_app

bp = Blueprint('social', __name__)

@bp.route('/api/feedback', methods=['GET'])
def get_feedback():
    input_user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = current_app.db
 
    query = """
        SELECT r.product_id, r.rating, r.comment, r.date_reviewed
        FROM Reviews r
        WHERE r.user_id == input_user_id
        ORDER BY r.date 
        LIMIT 5
    """
    try:
        items = db.execute(query, seller_id=int(seller_id))
    except Exception as e:
        current_app.logger.exception("DB error fetching reviews")
        return jsonify({"error": "database_error", "detail": str(e)}), 500

    columns = ['product_id', 'rating', 'comment', 'date']
    return jsonify([dict(zip(columns, row)) for row in items])