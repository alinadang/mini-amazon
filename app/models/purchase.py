from flask import current_app as app

class Purchase:
    def __init__(self, id, uid, pid, time_purchased):
        self.id = id
        self.uid = uid
        self.pid = pid
        self.time_purchased = time_purchased

    @staticmethod
    def get(id):
        rows = app.db.execute('''
SELECT id, uid, pid, time_purchased
FROM Purchases
WHERE id = :id
''',
                              id=id)
        return Purchase(*(rows[0])) if rows else None

    @staticmethod
    def get_all_by_uid_since(uid, since):
        rows = app.db.execute('''
SELECT id, uid, pid, time_purchased
FROM Purchases
WHERE uid = :uid
AND time_purchased >= :since
ORDER BY time_purchased DESC
''',
                              uid=uid,
                              since=since)
        return [Purchase(*row) for row in rows]


    @staticmethod
    def history_for_user(uid):
        """
        Return purchase history for a user, with product info and summary fields.
        Each row = one product purchased.
        """
        rows = app.db.execute('''
            SELECT
                p.id              AS purchase_id,
                p.time_purchased  AS time_purchased,
                pr.id             AS product_id,
                pr.name           AS product_name,
                pr.price          AS product_price,
                1                 AS num_items,      -- each purchase is 1 item
                'Fulfilled'       AS status
            FROM Purchases p
            JOIN Products pr ON p.pid = pr.id
            WHERE p.uid = :uid
            ORDER BY p.time_purchased DESC
        ''', uid=uid)

        #convert rows into dicts for easier template use
        history = []
        for r in rows:
            history.append({
                "purchase_id": r[0],
                "time_purchased": r[1],
                "product_id": r[2],
                "product_name": r[3],
                "product_price": float(r[4]),
                "num_items": int(r[5]),
                "status": r[6],
            })
        return history