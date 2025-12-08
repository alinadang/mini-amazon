from flask import render_template, redirect, url_for, flash, request
from werkzeug.urls import url_parse
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
from .models.user import User
from flask import jsonify
from .models.purchase import Purchase


from flask import Blueprint
bp = Blueprint('users', __name__)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_auth(form.email.data, form.password.data)
        if user is None:
            flash('Invalid email or password')
            return redirect(url_for('users.login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index.index')

        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


class RegistrationForm(FlaskForm):
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    address = StringField('Address')
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(),
            Length(min=6, message="Password must be at least 6 characters long.")
        ]
    )

    password2 = PasswordField(
        'Repeat Password',
        validators=[
            DataRequired(),
            EqualTo('password', message="Passwords must match.")
        ]
    )
    submit = SubmitField('Register')

    def validate_email(self, email):
        if User.email_exists(email.data):
            raise ValidationError('Already a user with this email.')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.register(form.email.data,
                         form.password.data,
                         form.firstname.data,
                         form.lastname.data, 
                         form.address.data):
            flash('Congratulations, you are now a registered user!')
            return redirect(url_for('users.login'))
    return render_template('register.html', title='Register', form=form)

"shows the settings account"
@bp.route('/settings', methods=['GET'])
@login_required
def account_settings():
    user = User.get(current_user.id)
    balance = User.get_balance(current_user.id)
    return render_template('account_settings.html', user=user, balance=balance)

@bp.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    #updating the user info: email, first and last name, and address
    email = request.form.get('email', '').strip()
    firstname = request.form.get('firstname', '').strip()
    lastname = request.form.get('lastname', '').strip()
    address = request.form.get('address', '').strip() or None

    #validation
    if not email or not firstname or not lastname:
        flash('Email, First Mame, and Last Name are required.', 'error')
        return redirect(url_for('users.account_settings'))
    #check for existing user 
    if email != current_user.email and User.email_exists(email):
        flash('This email already has an existing account.', 'error')
        return redirect(url_for('users.account_settings'))
    
    # if User.email_exists(email, exclude_user_id = current_user.id):
    #     flash('This email already has an existing account.', 'error')
    #     return redirect(url_for('users.account_settings'))

    #basic profile breakdown for updating
    good = User.update_profile(
        user_id = current_user.id,
        email = email,
        firstname = firstname,
        lastname = lastname,
        address = address
    )

    if not good:
        flash('ERROR: Updating profile failed. Please try again', 'error')
    else:
        flash('SUCCESS: successfully updated the profile', 'success')

    return redirect(url_for('users.account_settings'))

"password updates"
@bp.route('/settings/password', methods=['POST'])
@login_required
def update_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    #check for current password
    if not current_user.check_password(current_pw):
        flash('Incorrect current password', 'error')
        return redirect(url_for('users.account_settings'))
    
    #validating new password: 6 characters, confirmaation of pw --> can't update
    if not new_pw or len(new_pw) < 6:
        flash('New password needs to be at least 6 characters', 'error')
        return redirect(url_for('users.account_settings'))

    #confirming password
    if new_pw != confirm_pw:
        flash('Passwords do not match', 'error')
        return redirect(url_for('users.account_settings'))
    
    good = User.update_password(current_user.id, new_pw)
    if not good:
        flash('Error: Updating password failed. Please try again!', 'error')
    else:
        flash('Success: Updating password successful!', 'success')

    return redirect(url_for('users.account_settings'))

#balance updates
@bp.route('/settings/balance', methods=['POST'])
@login_required
def update_balance():
    #deposits and withdraws
    try:
        amount = float(request.form.get('amount', '0'))
    except ValueError:
        flash('Please enter a valid numeric value', 'error')
        return redirect(url_for('users.account_settings'))
    action = request.form.get('action')

    if amount <= 0:
        flash('Please enter a positive amount', 'error')
        return redirect(url_for('users.account_settings'))
    
    current_balance = User.get_balance(current_user.id)

    if action == 'withdraw':
        if amount > current_balance:
            flash("Insufficient balance, can not withdraw this amount", "error")
            return redirect(url_for('users.account_settings'))
        amount_changed = -amount

    elif action == 'deposit':
        amount_changed = amount
    else:
        flash('Invalid action', 'errpr')
        return redirect(url_for('users.account_settings'))
    
    good = User.update_balance(current_user.id, amount_changed)
    if not good:
        flash('Error: Updating balance failed. Please try again!', 'error')
    else:
        flash('Success: Balance updated', 'success')

    return redirect(url_for('users.account_settings'))


#user purchases
# @bp.route('/user_purchases')
# @login_required
# def user_purchases_page():
#     """Serve the user purchases page"""
#     purchases = Purchase.history_for_user(current_user.id)
#     return render_template('user_purchases.html')
@bp.route('/user_purchases')
@login_required
def user_purchases_page():
    """Show the logged-in user's purchase history with filtering."""
    # Get filter parameters
    sort_by = request.args.get('sort_by', 'date')
    sort_order = request.args.get('sort_order', 'desc')
    search_term = request.args.get('search', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status_filter = request.args.get('status', 'all')
    
    # Get purchase history
    purchases = Purchase.history_for_user(
        current_user.id,
        sort_by=sort_by,
        sort_order=sort_order,
        search_term=search_term,
        date_from=date_from,
        date_to=date_to,
        status_filter=status_filter
    )
    
    # Get summary stats
    summary = Purchase.get_purchase_summary(current_user.id)
    
    return render_template('user_purchases.html', 
                         purchases=purchases,
                         summary=summary,
                         sort_by=sort_by,
                         sort_order=sort_order,
                         search_term=search_term,
                         date_from=date_from,
                         date_to=date_to,
                         status_filter=status_filter)

@bp.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """Show detailed order page."""
    order_info = Purchase.get_order_details(order_id, current_user.id)
    
    if not order_info:
        flash('Order not found or you do not have permission to view it.', 'error')
        return redirect(url_for('users.user_purchases_page'))
    
    return render_template('order_details.html', order=order_info)

@bp.route('/user/<int:user_id>')
def public_profile(user_id):
    """Public view of a user's profile"""
    # Get the user
    user = User.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('index.index'))
    
    # Check if user is a seller
    is_seller = User.is_seller(user_id)
    
    return render_template('public_profile.html', 
                           user=user, 
                           is_seller=is_seller)

@bp.route('/users/search')
def search_users():
    """Simple user search (optional feature)"""
    query = request.args.get('q', '')
    users = []
    
    if query:
        rows = app.db.execute('''
            SELECT id, firstname, lastname, email
            FROM Users 
            WHERE firstname ILIKE :q OR lastname ILIKE :q OR email ILIKE :q
            LIMIT 20
        ''', q=f'%{query}%')
        
        for row in rows:
            users.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}",
                'email': row[3]
            })
    
    return render_template('search_users.html', users=users, query=query)

#user purchases api 
@bp.route('/api/user_purchases/<int:user_id>')
def get_user_purchases(user_id):
    """API endpoint to get user purchases with product details"""
    import datetime
    
    if user_id == 1:
        mock_purchases = [
            {
                'purchase_id': 1,
                'user_id': user_id,
                'product_id': 101,
                'time_purchased': datetime.datetime.now().isoformat(),
                'product_name': 'Wireless Bluetooth Headphones',
                'product_price': 99.99,
                'product_available': True
            },
            {
                'purchase_id': 2,
                'user_id': user_id,
                'product_id': 102,
                'time_purchased': (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(),
                'product_name': 'Laptop Stand',
                'product_price': 49.99,
                'product_available': True
            }
        ]
    elif user_id == 2:
        mock_purchases = [
            {
                'purchase_id': 3,
                'user_id': user_id,
                'product_id': 103,
                'time_purchased': (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
                'product_name': 'Mechanical Keyboard',
                'product_price': 129.99,
                'product_available': False
            }
        ]
    else:
        mock_purchases = [
            {
                'purchase_id': 4,
                'user_id': user_id,
                'product_id': 104,
                'time_purchased': (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat(),
                'product_name': 'USB-C Hub',
                'product_price': 39.99,
                'product_available': True
            }
        ]
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'purchases': mock_purchases
    })

#logging out
@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))

# Add these debug routes to app/users.py (not the model file!)

@bp.route('/debug/orders')
@login_required
def debug_orders():
    """Debug route to see what orders exist"""
    user_id = current_user.id
    
    # Check orders directly
    orders = app.db.execute('''
        SELECT id, order_date, status, total_amount, user_id
        FROM orders
        WHERE user_id = :user_id
        ORDER BY order_date DESC
    ''', user_id=user_id)
    
    # Check order items
    order_items = []
    if orders:
        for order in orders:
            items = app.db.execute('''
                SELECT oi.product_id, p.name, oi.price, oi.quantity
                FROM orderitems oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = :order_id
            ''', order_id=order[0])
            order_items.append({
                'order_id': order[0],
                'items': items
            })
    
    html = f"""
    <h3>Debug Orders for User {user_id}</h3>
    <h4>Found {len(orders)} orders:</h4>
    <table border="1">
        <tr>
            <th>Order ID</th>
            <th>Date</th>
            <th>Status</th>
            <th>Total</th>
        </tr>
    """
    
    for order in orders:
        html += f"""
        <tr>
            <td>{order[0]}</td>
            <td>{order[1]}</td>
            <td>{order[2]}</td>
            <td>${order[3] if order[3] else '0.00'}</td>
        </tr>
        """
    
    html += "</table>"
    
    html += "<h4>Order Items:</h4>"
    for order_info in order_items:
        html += f"<h5>Order {order_info['order_id']}:</h5>"
        if order_info['items']:
            html += "<ul>"
            for item in order_info['items']:
                html += f"<li>Product {item[0]} ({item[1]}): {item[3]} @ ${item[2]}</li>"
            html += "</ul>"
        else:
            html += "<p>No items found</p>"
    
    return html

@bp.route('/debug/db')
def debug_db():
    """Test database connections"""
    results = []
    
    # Test 1: Check Users table
    try:
        users = app.db.execute("SELECT COUNT(*) FROM users")
        results.append(f"Users table: {users[0][0]} rows")
    except Exception as e:
        results.append(f"Users table ERROR: {e}")
    
    # Test 2: Check Orders table
    try:
        orders = app.db.execute("SELECT COUNT(*) FROM orders")
        results.append(f"Orders table: {orders[0][0]} rows")
        
        # Show some sample orders
        sample_orders = app.db.execute("SELECT id, user_id, order_date, status FROM orders LIMIT 5")
        results.append(f"Sample orders: {sample_orders}")
    except Exception as e:
        results.append(f"Orders table ERROR: {e}")
    
    # Test 3: Check OrderItems table
    try:
        orderitems = app.db.execute("SELECT COUNT(*) FROM orderitems")
        results.append(f"OrderItems table: {orderitems[0][0]} rows")
    except Exception as e:
        results.append(f"OrderItems table ERROR: {e}")
    
    # Test 4: Check Products table
    try:
        products = app.db.execute("SELECT COUNT(*) FROM products")
        results.append(f"Products table: {products[0][0]} rows")
    except Exception as e:
        results.append(f"Products table ERROR: {e}")
    
    return "<br>".join(results)

@bp.route('/debug/cart')
@login_required
def debug_cart():
    """Debug cart issues"""
    user_id = current_user.id
    
    # Check user balance
    balance = User.get_balance(user_id)
    
    # Check cart items
    cart_items = app.db.execute('''
        SELECT ci.product_id, ci.quantity, p.name, p.price, p.available
        FROM cartitems ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.user_id = :user_id
    ''', user_id=user_id)
    
    # Check inventory if it exists
    try:
        inventory = app.db.execute('''
            SELECT product_id, quantity 
            FROM inventory 
            WHERE seller_id = :user_id
        ''', user_id=user_id)
    except:
        inventory = []
    
    return f"""
    <h3>Debug Info for User {user_id}</h3>
    <p>Balance: ${balance}</p>
    
    <h4>Cart Items ({len(cart_items)})</h4>
    <ul>
    {"".join([f'<li>{item[2]}: {item[1]} @ ${item[3]} (available: {item[4]})</li>' for item in cart_items])}
    </ul>
    
    <h4>Inventory ({len(inventory)})</h4>
    <ul>
    {"".join([f'<li>Product {item[0]}: {item[1]} in stock</li>' for item in inventory])}
    </ul>
    """