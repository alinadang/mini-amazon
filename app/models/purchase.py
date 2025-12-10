# app/models/purchase.py
from flask import current_app as app


class Purchase:
    """
    Helper methods for querying a user's purchases / orders.
    """

    @staticmethod
    def history_for_user(uid,
                         sort_by='date',
                         sort_order='desc',
                         search_term=None,
                         date_from=None,
                         date_to=None,
                         status_filter=None,
                         seller_filter=None):
        """
        Return purchase history for a user with filtering and sorting.
        Each row corresponds to one line item in an order.
        """
        # Base query
        query = '''
            SELECT
                o.id              AS order_id,
                o.order_date      AS time_purchased,
                oi.product_id     AS product_id,
                p.name            AS product_name,
                oi.price          AS product_price,
                oi.quantity       AS num_items,
                oi.fulfillment_status AS status,
                o.total_amount    AS order_total,
                p.creator_id      AS seller_id,
                u.firstname       AS seller_firstname,
                u.lastname        AS seller_lastname,
                oi.fulfilled_date AS fulfilled_date
            FROM orders o
            JOIN orderitems oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            LEFT JOIN users u ON p.creator_id = u.id
            WHERE o.user_id = :uid
        '''

        params = {'uid': uid}
        conditions = []

        # Status filter
        if status_filter and status_filter != 'all':
            conditions.append('oi.fulfillment_status = :status')
            params['status'] = status_filter

        # Product search
        if search_term:
            conditions.append('p.name ILIKE :search_term')
            params['search_term'] = f'%{search_term}%'

        # Date range
        if date_from:
            conditions.append('o.order_date >= :date_from')
            params['date_from'] = date_from

        if date_to:
            conditions.append('o.order_date <= :date_to')
            params['date_to'] = date_to

        # Seller filter
        if seller_filter:
            conditions.append('p.creator_id = :seller_id')
            try:
                params['seller_id'] = int(seller_filter)
            except ValueError:
                params['seller_id'] = -1  # will return nothing

        # Apply WHERE conditions
        if conditions:
            query += ' AND ' + ' AND '.join(conditions)

        # Sorting options
        sort_map = {
            'date': 'o.order_date',
            'amount': 'o.total_amount',
            'name': 'p.name',
            'status': 'oi.fulfillment_status',
            'quantity': 'oi.quantity',
            'seller': 'u.firstname'
        }
        sort_col = sort_map.get(sort_by, 'o.order_date')
        order_dir = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
        query += f' ORDER BY {sort_col} {order_dir}'

        try:
            rows = app.db.execute(query, **params)
        except Exception as e:
            print(f"ERROR in Purchase.history_for_user: {e}")
            print("Query:", query)
            print("Params:", params)
            return []

        history = []
        for r in rows:
            try:
                item_total = float(r[4]) * int(r[5])
            except Exception:
                item_total = 0.0

            seller_name = "Unknown Seller"
            if len(r) > 10 and r[9] and r[10]:
                seller_name = f"{r[9]} {r[10]}"

            history.append({
                "order_id": r[0],
                "time_purchased": r[1],
                "product_id": r[2],
                "product_name": r[3] if len(r) > 3 else "Unknown Product",
                "product_price": float(r[4]) if len(r) > 4 and r[4] else 0.0,
                "num_items": int(r[5]) if len(r) > 5 and r[5] else 1,
                "status": r[6] if len(r) > 6 and r[6] else "pending",
                "order_total": float(r[7]) if len(r) > 7 and r[7] else item_total,
                "item_total": item_total,
                "seller_id": r[8] if len(r) > 8 else None,
                "seller_name": seller_name,
                "fulfillment_date": r[11] if len(r) > 11 else None
            })

        return history

    @staticmethod
    def get_purchase_summary(uid):
        """Get summary stats for a user's purchases."""
        try:
            rows = app.db.execute('''
                SELECT 
                    COUNT(DISTINCT o.id) as total_orders,
                    COUNT(oi.id)        as total_items,
                    COALESCE(SUM(o.total_amount), 0) as total_spent,
                    COUNT(CASE WHEN oi.fulfillment_status = 'fulfilled' THEN o.id END) as fulfilled_orders,
                    COUNT(CASE WHEN oi.fulfillment_status = 'pending'   THEN o.id END) as pending_orders
                FROM orders o
                JOIN orderitems oi ON o.id = oi.order_id
                WHERE o.user_id = :uid
            ''', uid=uid)

            if rows and rows[0]:
                return {
                    'total_orders': rows[0][0],
                    'total_items': rows[0][1],
                    'total_spent': float(rows[0][2]),
                    'fulfilled_orders': rows[0][3],
                    'pending_orders': rows[0][4]
                }
        except Exception as e:
            print(f"Error getting purchase summary: {e}")

        return {
            'total_orders': 0,
            'total_items': 0,
            'total_spent': 0.0,
            'fulfilled_orders': 0,
            'pending_orders': 0
        }

    @staticmethod
    def get_spending_by_category(uid):
        """
        Total spending grouped by product category for this user.
        Used for "spending by category" cards in account settings.
        """
        try:
            rows = app.db.execute("""
                SELECT 
                    COALESCE(c.name, 'Uncategorized') AS category,
                    COALESCE(SUM(oi.price * oi.quantity), 0) AS total_spent,
                    COUNT(DISTINCT o.id) AS num_orders
                FROM orders o
                JOIN orderitems oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE o.user_id = :uid
                GROUP BY category
                ORDER BY total_spent DESC, category
            """, uid=uid)

            return [
                {
                    "category": r[0],
                    "total_spent": float(r[1]) if r[1] is not None else 0.0,
                    "num_orders": r[2],
                }
                for r in rows
            ]
        except Exception as e:
            print(f"Error getting spending by category: {e}")
            return []

    @staticmethod
    def get_spending_timeline(uid, limit=10):
        """
        Daily spending totals for this user (most recent N days with orders).
        Used for a small chart / history view in account settings.
        """
        try:
            rows = app.db.execute("""
                SELECT 
                    DATE(o.order_date) AS day,
                    COALESCE(SUM(oi.price * oi.quantity), 0) AS total_spent
                FROM orders o
                JOIN orderitems oi ON o.id = oi.order_id
                WHERE o.user_id = :uid
                GROUP BY DATE(o.order_date)
                ORDER BY day DESC
                LIMIT :limit
            """, uid=uid, limit=limit)

            # reverse so the chart goes oldest → newest
            rows = rows[::-1]

            return [
                {
                    "day": str(r[0]),
                    "total_spent": float(r[1]) if r[1] is not None else 0.0,
                }
                for r in rows
            ]
        except Exception as e:
            print(f"Error getting spending timeline: {e}")
            return []

    @staticmethod
    def get_order_details(order_id, uid=None):
        """
        Get detailed information for a specific order, including items.
        If uid is provided, enforce that the order belongs to that user.
        """
        try:
            query = '''
                SELECT
                    o.id AS order_id,
                    o.order_date,
                    o.total_amount,
                    oi.fulfillment_status,
                    oi.fulfilled_date,
                    oi.product_id,
                    p.name AS product_name,
                    p.image_url,
                    oi.price,
                    oi.quantity,
                    u.firstname || ' ' || u.lastname AS seller_name
                FROM orders o
                JOIN orderitems oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                LEFT JOIN users u ON p.creator_id = u.id
                WHERE o.id = :order_id
            '''

            params = {'order_id': order_id}

            if uid is not None:
                query += ' AND o.user_id = :uid'
                params['uid'] = uid

            rows = app.db.execute(query, **params)

            if not rows:
                return None

            order_info = {
                'order_id': rows[0][0],
                'order_date': rows[0][1],
                'total_amount': float(rows[0][2]) if rows[0][2] else 0.0,
                'status': rows[0][3],
                'fulfillment_date': rows[0][4],
                'items': []
            }

            for row in rows:
                price = float(row[8]) if row[8] else 0.0
                qty = row[9] if row[9] else 1
                order_info['items'].append({
                    'product_id': row[5],
                    'product_name': row[6],
                    'image_url': row[7],
                    'price': price,
                    'quantity': qty,
                    'seller_name': row[10],
                    'item_total': price * qty
                })

            return order_info

        except Exception as e:
            print(f"Error getting order details: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def get_status_counts(uid):
        """
        Get counts of orders by status (e.g., pending / fulfilled / cancelled).
        """
        try:
            rows = app.db.execute('''
                SELECT 
                    status,
                    COUNT(*) as count
                FROM orders
                WHERE user_id = :uid
                GROUP BY status
            ''', uid=uid)

            status_counts = {}
            for row in rows:
                status_counts[row[0]] = row[1]
            return status_counts

        except Exception as e:
            print(f"Error getting status counts: {e}")
            return {}
