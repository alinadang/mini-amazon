# app/models/review.py
from flask import current_app as app

class Review:
    @staticmethod
    def get_for_product(pid):
        rows = app.db.execute('''
SELECT R.review_id, R.rating, R.comment, R.date_reviewed, U.id, U.firstname, U.lastname
FROM Reviews R
LEFT JOIN Users U ON U.id = R.user_id
WHERE R.product_id = :pid
ORDER BY R.date_reviewed DESC
''', pid=pid)
        return [dict(review_id=r[0], rating=r[1], comment=r[2], date_reviewed=r[3], user_id=r[4], firstname=r[5], lastname=r[6]) for r in rows] if rows else []
