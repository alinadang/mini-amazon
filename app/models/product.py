from flask import current_app as app


class Product:
    def __init__(self, id, name, price, available, category, description, image_url, creator_id=None, total_sold=0):
        self.id = id
        self.name = name
        self.price = price
        self.available = available
        self.category = category
        self.description = description
        self.image_url = image_url
        self.creator_id = creator_id
        self.avg_rating = None
        self.total_sold = int(total_sold) if total_sold is not None else 0

    @staticmethod
    def _base_select():
        return '''
SELECT
  P.id,
  P.name,
  COALESCE(
    (SELECT MIN(i.seller_price) FROM Inventory i WHERE i.product_id = P.id AND i.quantity > 0),
    P.price
  )::numeric AS price,
  P.available,
  COALESCE(C.name, '') AS category,
  P.description,
  P.image_url,
  P.creator_id,
  COALESCE((SELECT SUM(oi.quantity) FROM OrderItems oi WHERE oi.product_id = P.id), 0) AS total_sold
FROM Products P
LEFT JOIN Categories C ON P.category_id = C.id
'''

    @staticmethod
    def _ensure_row_shape(row):
        r = list(row)
        if len(r) == 7:
            r.extend([None, 0])
        elif len(r) == 8:
            r.append(0)
        return r

    @staticmethod
    def get(id):
        rows = app.db.execute(Product._base_select() + 'WHERE P.id = :id', id=id)
        if rows:
            row = Product._ensure_row_shape(rows[0])
            return Product(*row)
        return None

    @staticmethod
    def get_all(available=True):
        rows = app.db.execute(Product._base_select() + 'WHERE P.available = :available', available=available)
        result = []
        if rows:
            for row in rows:
                row = Product._ensure_row_shape(row)
                result.append(Product(*row))
        return result

    @staticmethod
    def get_top_k(k=10):
        try:
            k = int(k)
            if k <= 0:
                k = 10
        except Exception:
            k = 10

        sql = Product._base_select() + 'ORDER BY price DESC LIMIT :k'
        rows = app.db.execute(sql, k=k)
        result = []
        if rows:
            for row in rows:
                row = Product._ensure_row_shape(row)
                result.append(Product(*row))
        return result

    @staticmethod
    def get_max_price():
        rows = app.db.execute('''
SELECT GREATEST(
  COALESCE((SELECT MAX(price) FROM Products), 0),
  COALESCE((SELECT MAX(seller_price) FROM Inventory), 0)
)
''')
        if rows and rows[0] and rows[0][0] is not None:
            try:
                return float(rows[0][0])
            except Exception:
                return 0.0
        return 0.0

    @staticmethod
    def get_page(page=1, per_page=50, sort='price', direction='desc',
                 q=None, category=None, available=True, ratings=None, min_price=None, max_price=None):
        try:
            page = max(1, int(page))
        except Exception:
            page = 1
        try:
            per_page = min(max(1, int(per_page)), 1000)
        except Exception:
            per_page = 50

        sort_map = {
            'price': 'price',
            'name': 'lower(P.name)',
            'id': 'P.id',
            'rating': None,
            'sales': None
        }
        sort_col = sort_map.get(sort, 'price')
        dir_sql = 'ASC' if str(direction).lower() == 'asc' else 'DESC'
        offset = (page - 1) * per_page

        where_clauses = ['P.available = :available']
        params = {'available': available}

        if q:
            q_str = q.strip()
            if q_str:
                where_clauses.append('(P.name ILIKE :q OR P.description ILIKE :q)')
                params['q'] = f'%{q_str}%'

        if category:
            where_clauses.append('(COALESCE(C.name, \'\') = :category)')
            params['category'] = category

        avg_rating_clauses = []
        if ratings:
            numeric_ranges = []
            include_no_reviews = False
            for rv in ratings:
                s = str(rv).strip()
                if s == 'no_reviews':
                    include_no_reviews = True
                else:
                    try:
                        v = int(s)
                        if 1 <= v <= 5:
                            if v == 5:
                                numeric_ranges.append((5.0, 5.0))
                            else:
                                numeric_ranges.append((float(v), float(v + 1)))
                    except Exception:
                        continue

            sub_parts = []
            idx = 0
            for lo, hi in numeric_ranges:
                if lo == hi:
                    pname = f'avg_eq_{idx}'
                    sub_parts.append(f"( (SELECT AVG(r.rating) FROM Reviews r WHERE r.product_id = P.id) = :{pname} )")
                    params[pname] = lo
                else:
                    pname_lo = f'avg_lo_{idx}'
                    pname_hi = f'avg_hi_{idx}'
                    sub_parts.append(f"( (SELECT AVG(r.rating) FROM Reviews r WHERE r.product_id = P.id) >= :{pname_lo} AND (SELECT AVG(r.rating) FROM Reviews r WHERE r.product_id = P.id) < :{pname_hi} )")
                    params[pname_lo] = lo
                    params[pname_hi] = hi
                idx += 1

            if include_no_reviews:
                sub_parts.append('NOT EXISTS (SELECT 1 FROM Reviews r2 WHERE r2.product_id = P.id)')

            if sub_parts:
                avg_rating_clauses.append('(' + ' OR '.join(sub_parts) + ')')

        if avg_rating_clauses:
            where_clauses.append('(' + ' AND '.join(avg_rating_clauses) + ')')

        price_expr = "COALESCE((SELECT MIN(i.seller_price) FROM Inventory i WHERE i.product_id = P.id AND i.quantity > 0), P.price)"
        if min_price is not None:
            try:
                min_v = float(min_price)
                where_clauses.append(f"({price_expr}) >= :min_price")
                params['min_price'] = min_v
            except Exception:
                pass
        if max_price is not None:
            try:
                max_v = float(max_price)
                where_clauses.append(f"({price_expr}) <= :max_price")
                params['max_price'] = max_v
            except Exception:
                pass

        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'

        count_sql = f'''
SELECT COUNT(*)
FROM Products P
LEFT JOIN Categories C ON P.category_id = C.id
WHERE {where_sql}
'''
        total_row = app.db.execute(count_sql, **params)
        total = total_row[0][0] if total_row else 0

        if sort == 'rating':
            order_sql = f'''
ORDER BY (
  SELECT COALESCE(AVG(r.rating), 0)
  FROM Reviews r
  WHERE r.product_id = P.id
) {dir_sql}
'''
        elif sort == 'sales':
            order_sql = f'ORDER BY COALESCE((SELECT SUM(oi.quantity) FROM OrderItems oi WHERE oi.product_id = P.id),0) {dir_sql}'
        else:
            order_sql = f'ORDER BY {sort_col} {dir_sql}'

        page_sql = f'''
{Product._base_select()}
WHERE {where_sql}
{order_sql}
LIMIT :limit OFFSET :offset
'''
        params.update({'limit': per_page, 'offset': offset})

        rows = app.db.execute(page_sql, **params)

        items = []
        if rows:
            for row in rows:
                row = Product._ensure_row_shape(row)
                items.append(Product(*row))

        return items, total

    @staticmethod
    def get_categories():
        rows = app.db.execute('''
SELECT name FROM Categories
WHERE name IS NOT NULL AND name <> ''
ORDER BY name
''')
        return [r[0] for r in rows] if rows else []