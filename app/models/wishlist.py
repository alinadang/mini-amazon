from flask import current_app as app


class WishlistItem:
    def __init__(self, id, uid, pid, time_added):
        self.id = id
        self.uid = uid
        self.pid = pid
        self.time_added = time_added

    @staticmethod
    def get(id):
        rows = app.db.execute(
            '''
            SELECT id, uid, pid, time_added
            FROM Wishes
            WHERE id = :id
            ''',
            id=id,
        )
        return WishlistItem(*(rows[0])) if rows else None

    @staticmethod
    def get_all_by_uid(uid):
        """
        Return wishlist entries for a user, joined with product info,
        as dicts so templates can use item.name, item.price, item.image_url.
        """
        rows = app.db.execute(
            '''
            SELECT w.id,
                   w.uid,
                   w.pid,
                   w.time_added,
                   p.name,
                   p.price,
                   p.image_url
            FROM Wishes w
            JOIN Products p ON w.pid = p.id
            WHERE w.uid = :uid
            ORDER BY w.time_added DESC
            ''',
            uid=uid,
        )

        return [
            {
                "id": r[0],
                "uid": r[1],
                "pid": r[2],
                "time_added": r[3],
                "name": r[4],
                "price": r[5],
                "image_url": r[6],
            }
            for r in rows
        ]

    @staticmethod
    def add(uid, pid):
        """Add a new item to the user's wishlist, ignoring duplicates."""
        try:
            rows = app.db.execute(
                '''
                INSERT INTO Wishes(uid, pid, time_added)
                VALUES(:uid, :pid, (current_timestamp AT TIME ZONE 'UTC'))
                ON CONFLICT (uid, pid) DO UPDATE
                    SET time_added = EXCLUDED.time_added
                RETURNING id
                ''',
                uid=uid,
                pid=pid,
            )
            return WishlistItem.get(rows[0][0])
        except Exception as e:
            print("Error adding to wishlist:", e)
            return None

    @staticmethod
    def remove(uid, pid):
        """Remove a product from the user's wishlist."""
        try:
            app.db.execute(
                '''
                DELETE FROM Wishes
                WHERE uid = :uid AND pid = :pid
                ''',
                uid=uid,
                pid=pid,
            )
            return True
        except Exception as e:
            print("Error removing from wishlist:", e)
            return False