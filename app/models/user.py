from flask_login import UserMixin
from flask import current_app as app
from werkzeug.security import generate_password_hash, check_password_hash

from .. import login


class User(UserMixin):
    def __init__(self, id, email, firstname, lastname, address=None, balance=0.0):
        self.id = id
        self.email = email
        self.firstname = firstname
        self.lastname = lastname
        self.address = address
        self.balance = float(balance) if balance else 0.0

    def check_password(self, password):
        """Check if provided password matches user's password"""
        rows = app.db.execute("""
            SELECT password
            FROM Users
            WHERE id = :id
        """, id=self.id)
        if rows:
            return check_password_hash(rows[0][0], password)
        return False

    @staticmethod
    def get_by_auth(email, password):
        rows = app.db.execute("""
SELECT password, id, email, firstname, lastname, address, balance
FROM Users
WHERE email = :email
""",
                              email=email)
        if not rows:  # email not found
            return None
        elif not check_password_hash(rows[0][0], password):
            # incorrect password
            return None
        else:
            return User(*(rows[0][1:]))

    @staticmethod
    def email_exists(email, exclude_user_id=None):
        """Check if email already exists (optionally excluding a specific user)"""
        if exclude_user_id:
            rows = app.db.execute("""
SELECT email
FROM Users
WHERE email = :email AND id != :user_id
""",
                                  email=email,
                                  user_id=exclude_user_id)
        else:
            rows = app.db.execute("""
SELECT email
FROM Users
WHERE email = :email
""",
                                  email=email)
        return len(rows) > 0

    @staticmethod
    def register(email, password, firstname, lastname, address=None):
        try:
            rows = app.db.execute("""
INSERT INTO Users(email, password, firstname, lastname, address)
VALUES(:email, :password, :firstname, :lastname, :address)
RETURNING id
""",
                                  email=email,
                                  password=generate_password_hash(password),
                                  firstname=firstname,
                                  lastname=lastname,
                                  address=address)
            id = rows[0][0]
            return User.get(id)
        except Exception as e:
            # likely email already in use; better error checking and reporting needed;
            # the following simply prints the error to the console:
            print(str(e))
            return None

    @staticmethod
    @login.user_loader
    def get(id):
        rows = app.db.execute("""
SELECT id, email, firstname, lastname, address, balance
FROM Users
WHERE id = :id
""",
                              id=id)
        return User(*(rows[0])) if rows else None
    
#     @staticmethod
#     def get(id):
#         rows = app.db.execute("""
# SELECT id, email, password, firstname, lastname, balance
# FROM Users
# WHERE id = :id
# """, id=id)
#         return User(*rows[0]) if rows else None


    @staticmethod
    def update_profile(user_id, email, firstname, lastname, address):
        """Update user profile information (not password)"""
        try:
            app.db.execute('''
UPDATE Users
SET email = :email,
    firstname = :firstname,
    lastname = :lastname,
    address = :address
WHERE id = :user_id
''',
                user_id=user_id,
                email=email,
                firstname=firstname,
                lastname=lastname,
                address=address)
            return True
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False

    @staticmethod
    def update_password(user_id, new_password):
        """Update user password"""
        try:
            app.db.execute('''
UPDATE Users
SET password = :password
WHERE id = :user_id
''',
                user_id=user_id,
                password=generate_password_hash(new_password))
            return True
        except Exception as e:
            print(f"Error updating password: {e}")
            return False

    @staticmethod
    def update_balance(user_id, amount_change):
        """Add or subtract from user balance"""
        try:
            app.db.execute('''
UPDATE Users
SET balance = balance + :amount_change
WHERE id = :user_id
''',
                user_id=user_id,
                amount_change=amount_change)
            return True
        except Exception as e:
            print(f"Error updating balance: {e}")
            return False

    @staticmethod
    def get_balance(user_id):
        """Get current balance"""
        rows = app.db.execute('''
SELECT balance
FROM Users
WHERE id = :user_id
''', user_id=user_id)
        return float(rows[0][0]) if rows else 0.0