# app/models/inventory.py
from flask import current_app as app

class Inventory:
    @staticmethod
    def get_for_product(pid):
        rows = app.db.execute('''
SELECT I.seller_id, I.quantity, I.seller_price, U.firstname, U.lastname
FROM Inventory I
JOIN Users U ON U.id = I.seller_id
WHERE I.product_id = :pid
ORDER BY I.seller_price ASC
''', pid=pid)
        return [dict(seller_id=r[0], quantity=r[1], seller_price=r[2], firstname=r[3], lastname=r[4]) for r in rows] if rows else []
    