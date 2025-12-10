# app/models/purchase.py
from flask import current_app as app

class Purchase:
#     def __init__(self, id, uid, pid, time_purchased):
#         self.id = id
#         self.uid = uid
#         self.pid = pid
#         self.time_purchased = time_purchased

#     @staticmethod
#     def get(id):
#         rows = app.db.execute('''
# SELECT id, uid, pid, time_purchased
# FROM Purchases
# WHERE id = :id
# ''',
#                               id=id)
#         return Purchase(*(rows[0])) if rows else None

#     @staticmethod
#     def get_all_by_uid_since(uid, since):
#         rows = app.db.execute('''
# SELECT id, uid, pid, time_purchased
# FROM Purchases
# WHERE uid = :uid
# AND time_purchased >= :since
# ORDER BY time_purchased DESC
# ''',
#                               uid=uid,
#                               since=since)
#         return [Purchase(*row) for row in rows]

    @staticmethod
    def history_for_user(uid, sort_by='date', sort_order='desc', 
                        search_term=None, date_from=None, date_to=None, 
                        status_filter=None, seller_filter=None):
        """ Return purchase history for a user with filtering and sorting.
        """
        print(f"=== DEBUG in history_for_user ===")
        print(f"uid parameter received = {uid}")
        print(f"uid type = {type(uid)}")
        
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
        
        # Add filters
        if status_filter and status_filter != 'all':
            conditions.append('oi.fulfillment_status = :status')
            params['status'] = status_filter
        
        if search_term:
            conditions.append('p.name ILIKE :search_term')
            params['search_term'] = f'%{search_term}%'
        
        if date_from:
            conditions.append('o.order_date >= :date_from')
            params['date_from'] = date_from
        
        if date_to:
            conditions.append('o.order_date <= :date_to')
            params['date_to'] = date_to
        
        # Add seller filter
        if seller_filter:
            conditions.append('p.creator_id = :seller_id')
            params['seller_id'] = int(seller_filter)
        
        # Apply conditions
        if conditions:
            query += ' AND ' + ' AND '.join(conditions)
        
        # Add sorting
        sort_map = {
            'date': 'o.order_date',
            'amount': 'o.total_amount',
            'name': 'p.name',
            'status': 'oi.fulfillment_status',
            'quantity': 'oi.quantity',
            'seller': 'u.firstname'
        }
        
        sort_col = sort_map.get(sort_by, 'o.order_date')
        order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
        
        query += f' ORDER BY {sort_col} {order}'
        
        try:
            print(f"DEBUG: Executing query: {query}")
            print(f"DEBUG: With params: {params}")
            rows = app.db.execute(query, **params)
            print(f"DEBUG: Got {len(rows)} rows")
        except Exception as e:
            print(f"ERROR in purchase history query: {e}")
            print(f"ERROR: Query was: {query}")
            return []
        
        # Convert rows into dicts
        history = []
        for r in rows:
            try:
                item_total = float(r[4]) * int(r[5])
            except (TypeError, IndexError):
                item_total = 0.0
            
            history.append({
                "order_id": r[0],
                "time_purchased": r[1],
                "product_id": r[2],
                "product_name": r[3] if len(r) > 3 else "Unknown Product",
                "product_price": float(r[4]) if len(r) > 4 and r[4] else 0.0,
                "num_items": int(r[5]) if len(r) > 5 and r[5] else 1,
                "status": r[6] if len(r) > 6 else "pending",
                "order_total": float(r[7]) if len(r) > 7 and r[7] else item_total,
                "item_total": item_total,
                "seller_id": r[8] if len(r) > 8 else None,
                "seller_name": f"{r[9]} {r[10]}" if len(r) > 10 and r[9] and r[10] else "Unknown Seller",
                "fulfillment_date": r[11] if len(r) > 11 else None
            })
        return history

    @staticmethod
    def get_purchase_summary(uid):
        """Get summary stats for user's purchases"""
        try:
            rows = app.db.execute('''
                SELECT 
                    COUNT(DISTINCT o.id) as total_orders,
                    COUNT(oi.id) as total_items,
                    COALESCE(SUM(o.total_amount), 0) as total_spent,
                    COUNT(CASE WHEN oi.fulfillment_status = 'fulfilled' THEN o.id END) as fulfilled_orders,
                    COUNT(CASE WHEN oi.fulfillment_status = 'pending' THEN o.id END) as pending_orders
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
            'total_spent': 0, 
            'fulfilled_orders': 0,
            'pending_orders': 0
        }

    @staticmethod
    def get_order_details(order_id, uid=None):
        """
        Get detailed information for a specific order.
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
            
            if uid:
                query += ' AND o.user_id = :uid'
                params['uid'] = uid
            
            rows = app.db.execute(query, **params)
            
            if not rows:
                return None
            
            # Group items by order
            order_info = {
                'order_id': rows[0][0],
                'order_date': rows[0][1],
                'total_amount': float(rows[0][2]) if rows[0][2] else 0,
                'status': rows[0][3],
                'fulfillment_date': rows[0][4],
                'items': []
            }
            
            for row in rows:
                order_info['items'].append({
                    'product_id': row[5],
                    'product_name': row[6],
                    'image_url': row[7],
                    'price': float(row[8]) if row[8] else 0,
                    'quantity': row[9] if row[9] else 1,
                    'seller_name': row[10],
                    'item_total': float(row[8]) * row[9] if row[8] and row[9] else 0
                })
            
            return order_info
        except Exception as e:
            print(f"Error getting order details: {e}")
            import traceback
            traceback.print_exc()  # This will help debug if there are other issues
            return None

    @staticmethod
    def get_status_counts(uid):
        """Get counts of orders by status"""
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