from flask import current_app as app


class Product:
    def __init__(self, id, name, price, available):
        self.id = id
        self.name = name
        self.price = price
        self.available = available
        """self.category = category
        self.description = description
        self.image_url = image_url"""


    @staticmethod
    def get(id):
        rows = app.db.execute('''
SELECT id, name, price, available
FROM Products
WHERE id = :id
''',
                              id=id)
        return Product(*(rows[0])) if rows is not None else None

    @staticmethod
    def get_all(available=True):
        rows = app.db.execute('''
SELECT id, name, price, available
FROM Products
WHERE available = :available
''',
                              available=available)
        return [Product(*row) for row in rows]

    @staticmethod
    def get_top_k(k=10):

        try:
            k = int(k)
            if k <= 0:
                k = 10
        except Exception:
            k = 10

        rows = app.db.execute('''
SELECT id, name, price, available
FROM Products
ORDER BY price DESC
LIMIT :k
''', k=k)
        return [Product(*row) for row in rows] if rows else []
    @staticmethod
    def get_page(page=1, per_page=50, sort='price', direction='desc',
                 q=None, available=True):
        """
        Return (items, total_count).
        """
        try:
            page = int(page)
            if page < 1:
                page = 1
        except Exception:
            page = 1
        try:
            per_page = int(per_page)
            if per_page < 1 or per_page > 1000:
                per_page = 50
        except Exception:
            per_page = 50

        sort_map = {
            'price': 'price',
            'name': 'lower(name)',
            'id': 'id'
        }
        sort_col = sort_map.get(sort, 'price')
        dir_sql = 'ASC' if str(direction).lower() == 'asc' else 'DESC'

        offset = (page - 1) * per_page

        select_clause = "id, name, price, available"

        where_clauses = ["available = :available"]
        params = {'available': available}

        # keyword search
        if q:
            qs = q.strip()
            if qs:
                where_clauses.append("name ILIKE :q")
                params['q'] = f"%{qs}%"

        where_sql = " AND ".join(where_clauses)

        count_sql = f"SELECT COUNT(*) FROM Products WHERE {where_sql}"
        total_row = app.db.execute(count_sql, **params)
        total = total_row[0][0] if total_row else 0

        # page SQL
        page_sql = f"""
SELECT {select_clause}
FROM Products
WHERE {where_sql}
ORDER BY {sort_col} {dir_sql}
LIMIT :limit OFFSET :offset
"""
        params.update({'limit': per_page, 'offset': offset})
        rows = app.db.execute(page_sql, **params)
        items = [Product(*row) for row in rows] if rows else []
        return items, total

