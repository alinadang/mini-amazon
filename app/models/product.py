# app/models/product.py
from flask import current_app as app


class Product:
    def __init__(self, id, name, price, available, category, description, image_url):
        """
        Note: 'category' here is the category *name* (text), joined from Categories.
        """
        self.id = id
        self.name = name
        self.price = price
        self.available = available
        self.category = category
        self.description = description
        self.image_url = image_url

    @staticmethod
    def _base_select():
        # returns SELECT ... FROM Products P LEFT JOIN Categories C ...
        return '''
SELECT P.id, P.name, P.price, P.available,
       COALESCE(C.name, '') AS category,
       P.description, P.image_url
FROM Products P
LEFT JOIN Categories C ON P.category_id = C.id
'''

    @staticmethod
    def get(id):
        rows = app.db.execute(Product._base_select() + 'WHERE P.id = :id', id=id)
        return Product(*rows[0]) if rows else None

    @staticmethod
    def get_all(available=True):
        rows = app.db.execute(Product._base_select() + 'WHERE P.available = :available', available=available)
        return [Product(*row) for row in rows] if rows else []

    @staticmethod
    def get_top_k(k=10):
        try:
            k = int(k)
            if k <= 0:
                k = 10
        except Exception:
            k = 10

        sql = Product._base_select() + 'ORDER BY P.price DESC LIMIT :k'
        rows = app.db.execute(sql, k=k)
        return [Product(*row) for row in rows] if rows else []

    @staticmethod
    def get_categories():
        """Return a list of category names (strings), ordered alphabetically."""
        rows = app.db.execute('''
SELECT name FROM Categories
WHERE name IS NOT NULL AND name <> ''
ORDER BY name
''')
        return [r[0] for r in rows] if rows else []

    @staticmethod
    def get_page(page=1, per_page=50, sort='price', direction='desc',
                 q=None, category=None, available=True):
        """
        Return (items, total_count).
        Filters by category name (passed in `category`) if provided.
        Supports searching name or description via q.
        """
        try:
            page = max(1, int(page))
        except Exception:
            page = 1
        try:
            per_page = min(max(1, int(per_page)), 1000)
        except Exception:
            per_page = 50

        sort_map = {
            'price': 'P.price',
            'name': 'lower(P.name)',
            'id': 'P.id'
        }
        sort_col = sort_map.get(sort, 'P.price')
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
            # category is a name; join exists already in base_select, so filter on C.name
            where_clauses.append('(COALESCE(C.name, \'\') = :category)')
            params['category'] = category

        where_sql = ' AND '.join(where_clauses)

        # total count (must count matching rows)
        count_sql = f'''
SELECT COUNT(*)
FROM Products P
LEFT JOIN Categories C ON P.category_id = C.id
WHERE {where_sql}
'''
        total_row = app.db.execute(count_sql, **params)
        total = total_row[0][0] if total_row else 0

        page_sql = f'''
{Product._base_select()}
WHERE {where_sql}
ORDER BY {sort_col} {dir_sql}
LIMIT :limit OFFSET :offset
'''
        params.update({'limit': per_page, 'offset': offset})
        rows = app.db.execute(page_sql, **params)
        items = [Product(*row) for row in rows] if rows else []
        return items, total
