from flask import render_template, redirect, url_for, flash, request
from urllib.parse import urlparse
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
from .models.user import User
from flask import jsonify
from .models.purchase import Purchase
from flask import current_app as app

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
        if not next_page or urlparse(next_page).netloc != '':
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


@bp.route('/settings', methods=['GET'])
@login_required
def account_settings():
    user = User.get(current_user.id)
    balance = User.get_balance(current_user.id)

    # overall purchase stats for this user
    purchase_summary = Purchase.get_purchase_summary(current_user.id)

    # new: breakdowns for visualization
    spending_by_category = Purchase.get_spending_by_category(current_user.id)
    spending_timeline = Purchase.get_spending_timeline(current_user.id, limit=10)

    return render_template(
        'account_settings.html',
        user=user,
        balance=balance,
        purchase_summary=purchase_summary,
        spending_by_category=spending_by_category,
        spending_timeline=spending_timeline,
    )


@bp.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    email = request.form.get('email', '').strip()
    firstname = request.form.get('firstname', '').strip()
    lastname = request.form.get('lastname', '').strip()
    address = request.form.get('address', '').strip() or None

    if not email or not firstname or not lastname:
        flash('Email, First Name, and Last Name are required.', 'error')
        return redirect(url_for('users.account_settings'))
    
    if email != current_user.email and User.email_exists(email):
        flash('This email already has an existing account.', 'error')
        return redirect(url_for('users.account_settings'))

    good = User.update_profile(
        user_id=current_user.id,
        email=email,
        firstname=firstname,
        lastname=lastname,
        address=address
    )

    if not good:
        flash('ERROR: Updating profile failed. Please try again', 'error')
    else:
        flash('SUCCESS: Successfully updated the profile', 'success')

    return redirect(url_for('users.account_settings'))


@bp.route('/settings/password', methods=['POST'])
@login_required
def update_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        flash('Incorrect current password', 'error')
        return redirect(url_for('users.account_settings'))
    
    if not new_pw or len(new_pw) < 6:
        flash('New password needs to be at least 6 characters', 'error')
        return redirect(url_for('users.account_settings'))

    if new_pw != confirm_pw:
        flash('Passwords do not match', 'error')
        return redirect(url_for('users.account_settings'))
    
    good = User.update_password(current_user.id, new_pw)
    if not good:
        flash('Error: Updating password failed. Please try again!', 'error')
    else:
        flash('Success: Updating password successful!', 'success')

    return redirect(url_for('users.account_settings'))


@bp.route('/settings/balance', methods=['POST'])
@login_required
def update_balance():
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
            flash("Insufficient balance, cannot withdraw this amount", "error")
            return redirect(url_for('users.account_settings'))
        amount_changed = -amount
    elif action == 'deposit':
        amount_changed = amount
    else:
        flash('Invalid action', 'error')
        return redirect(url_for('users.account_settings'))
    
    good = User.update_balance(current_user.id, amount_changed)
    if not good:
        flash('Error: Updating balance failed. Please try again!', 'error')
    else:
        flash('Success: Balance updated', 'success')

    return redirect(url_for('users.account_settings'))


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
    seller_filter = request.args.get('seller', '')  # ADD THIS LINE
    
    # Get purchase history - now include seller_filter
    purchases = Purchase.history_for_user(
        current_user.id,
        sort_by=sort_by,
        sort_order=sort_order,
        search_term=search_term,
        date_from=date_from,
        date_to=date_to,
        status_filter=status_filter,
        seller_filter=seller_filter  # ADD THIS LINE
    )
    
    summary = Purchase.get_purchase_summary(current_user.id)
    
    # Get list of sellers user has purchased from for dropdown
    sellers = get_user_sellers(current_user.id)
    
    return render_template('user_purchases.html', 
                         purchases=purchases,
                         summary=summary,
                         sellers=sellers,
                         sort_by=sort_by,
                         sort_order=sort_order,
                         search_term=search_term,
                         date_from=date_from,
                         date_to=date_to,
                         status_filter=status_filter,
                         seller_filter=seller_filter)


@bp.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """Show detailed order page."""
    order_info = Purchase.get_order_details(order_id, current_user.id)
    
    if not order_info:
        flash('Order not found or you do not have permission to view it.', 'error')
        return redirect(url_for('users.user_purchases_page'))
    
    return render_template('order_details.html', order=order_info)


# ============================================================================
# PUBLIC PROFILE HELPER FUNCTIONS
# ============================================================================

def get_seller_statistics(seller_id):
    """Get statistics for a seller - gracefully handles missing tables"""
    try:
        # Get total products
        product_count = app.db.execute('''
            SELECT COUNT(*) FROM products WHERE creator_id = :seller_id
        ''', seller_id=seller_id)[0][0]
        
        # Get total sales
        sales_data = app.db.execute('''
            SELECT COUNT(DISTINCT o.id) as order_count,
                   COALESCE(SUM(oi.quantity), 0) as items_sold,
                   COALESCE(SUM(oi.price * oi.quantity), 0) as total_revenue
            FROM orders o
            JOIN orderitems oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE p.creator_id = :seller_id
            AND oi.fulfillment_status = 'fulfilled'
        ''', seller_id=seller_id)
        
        # Try to get reviews (gracefully fail if table doesn't exist)
        try:
            rating_data = app.db.execute('''
                SELECT AVG(r.rating) as avg_rating, COUNT(*) as review_count
                FROM reviews r
                JOIN products p ON r.product_id = p.id
                WHERE p.creator_id = :seller_id
            ''', seller_id=seller_id)
            avg_rating = float(rating_data[0][0]) if rating_data and rating_data[0][0] else 0.0
            review_count = rating_data[0][1] if rating_data else 0
        except:
            avg_rating = 0.0
            review_count = 0
        
        # Get fulfillment rate
        fulfillment_data = app.db.execute('''
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN oi.fulfillment_status = 'fulfilled' THEN 1 END) as fulfilled
            FROM orderitems oi
            JOIN products p ON oi.product_id = p.id
            WHERE p.creator_id = :seller_id
        ''', seller_id=seller_id)
        
        return {
            'product_count': product_count,
            'order_count': sales_data[0][0] if sales_data else 0,
            'items_sold': sales_data[0][1] if sales_data else 0,
            'total_revenue': float(sales_data[0][2]) if sales_data else 0.0,
            'avg_rating': avg_rating,
            'review_count': review_count,
            'fulfillment_rate': (fulfillment_data[0][1] / fulfillment_data[0][0] * 100) if fulfillment_data and fulfillment_data[0][0] > 0 else 0
        }
    except Exception as e:
        print(f"Error getting seller statistics: {e}")
        return None


def get_seller_reviews(seller_id):
    """
    Get *seller* reviews for a seller from SellerReviews.

    This returns a list of dicts that work for BOTH:
    - seller_profile.html (uses rating/comment/date_reviewed/reviewer_name)
    - public_profile.html (uses reviewer_id, review_text, created_at, etc.)
    """
    try:
        rows = app.db.execute('''
            SELECT
                sr.id,
                sr.rating,
                sr.comment,
                sr.date_reviewed,
                u.id AS reviewer_id,
                u.firstname,
                u.lastname
            FROM SellerReviews sr
            JOIN Users u ON sr.user_id = u.id
            WHERE sr.seller_id = :seller_id
            ORDER BY sr.date_reviewed DESC
        ''', seller_id=seller_id)

        reviews = []
        for row in rows:
            reviews.append({
                'id': row[0],
                'rating': int(row[1]),
                'comment': row[2],
                'review_text': row[2],        # for public_profile compatibility
                'date_reviewed': row[3],
                'created_at': row[3],         # for public_profile compatibility
                'reviewer_id': row[4],
                'reviewer_name': (
                    f"{row[5]} {row[6][0]}." if row[6] else row[5]
                ),
                # product fields no longer applicable, but public_profile doesn't *need* them
                'product_id': None,
                'product_name': None,
            })
        return reviews

    except Exception as e:
        print(f"SellerReviews table not available or error: {e}")
        return []




def get_user_sellers(user_id):
    """Get list of sellers that this user has purchased from"""
    try:
        rows = app.db.execute("""
            SELECT DISTINCT oi.seller_id, u.firstname, u.lastname
            FROM orders o
            JOIN orderitems oi ON o.id = oi.order_id
            JOIN users u ON oi.seller_id = u.id
            WHERE o.user_id = :user_id
            ORDER BY u.firstname, u.lastname
        """, user_id=user_id)

        sellers = []
        for row in rows:
            sellers.append({
                'id': row[0],
                'name': f"{row[1]} {row[2]}"
            })
        return sellers
    except Exception as e:
        print(f"Error getting user sellers: {e}")
        return []



@bp.route('/user/<int:user_id>')
def public_profile(user_id):
    """Public view of a user's profile - shows account info, and for sellers: contact info and reviews"""
    user = User.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('index.index'))
    
    is_seller = User.is_seller(user_id)
    buyer_summary = Purchase.get_purchase_summary(user_id)

    seller_stats = None
    reviews = []
    has_purchased_from_seller = False
    my_seller_review = None

    if is_seller:
        seller_stats = get_seller_statistics(user_id)
        reviews = get_seller_reviews(user_id)

        if current_user.is_authenticated and current_user.id != user_id:
            # has this user ever ordered from this seller?
            sellers_bought = get_user_sellers(current_user.id)
            has_purchased_from_seller = any(s['id'] == user_id for s in sellers_bought)

            # does this user already have a review?
            for r in reviews:
                if r.get('reviewer_id') == current_user.id:
                    my_seller_review = r
                    break
    
    return render_template(
        'public_profile.html', 
        user=user, 
        is_seller=is_seller,
        buyer_summary=buyer_summary,
        seller_stats=seller_stats,
        reviews=reviews,
        has_purchased_from_seller=has_purchased_from_seller,
        my_seller_review=my_seller_review,
    )


@bp.route('/users/search')
def search_users():
    """
    Sellers directory page with optional search.
    """
    query = request.args.get('q', '').strip()

    sellers = User.get_sellers(query=query)
    all_sellers = User.get_sellers()
    total_sellers = len(all_sellers)

    is_current_seller = False
    if current_user.is_authenticated:
        is_current_seller = User.is_seller(current_user.id)

    return render_template(
        'search_users.html',
        sellers=sellers,
        total_sellers=total_sellers,
        query=query,
        is_current_seller=is_current_seller,
    )

@bp.route('/user/<int:seller_id>/review', methods=['GET', 'POST'])
@login_required
def seller_review(seller_id):
    """Create or update a review for a seller, if user has ordered from them."""
    # can't review yourself
    if seller_id == current_user.id:
        flash("You can't review yourself.", "error")
        return redirect(url_for('users.public_profile', user_id=seller_id))

    seller = User.get(seller_id)
    if not seller:
        flash('Seller not found.', 'error')
        return redirect(url_for('index.index'))

    # ---- check that current user has ordered from this seller ----
    has_order = app.db.execute("""
        SELECT 1
        FROM orders o
        JOIN orderitems oi ON o.id = oi.order_id
        WHERE o.user_id = :uid
          AND oi.seller_id = :sid
        LIMIT 1
    """, uid=current_user.id, sid=seller_id)

    if not has_order:
        flash('You can only review sellers you have purchased from.', 'error')
        return redirect(url_for('users.public_profile', user_id=seller_id))

    # GET → show form (pre-filled if an existing review)
    if request.method == 'GET':
        existing = None
        rows = app.db.execute("""
            SELECT rating, comment
            FROM SellerReviews
            WHERE seller_id = :sid AND user_id = :uid
            LIMIT 1
        """, sid=seller_id, uid=current_user.id)
        if rows:
            existing = {
                "rating": int(rows[0][0]),
                "comment": rows[0][1] or ""
            }
        return render_template('seller_review_form.html',
                               seller=seller,
                               existing=existing)

    # POST → insert or update (single review per (seller, user))
    rating_raw = request.form.get('rating')
    comment = (request.form.get('comment') or '').strip()

    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except Exception:
        flash('Rating must be an integer between 1 and 5.', 'error')
        return redirect(url_for('users.seller_review', seller_id=seller_id))

    try:
        existing = app.db.execute("""
            SELECT id
            FROM SellerReviews
            WHERE seller_id = :sid AND user_id = :uid
            LIMIT 1
        """, sid=seller_id, uid=current_user.id)

        if existing:
            # update existing
            app.db.execute("""
                UPDATE SellerReviews
                SET rating = :rating,
                    comment = :comment,
                    date_reviewed = NOW()
                WHERE seller_id = :sid AND user_id = :uid
            """, rating=rating, comment=comment or None,
               sid=seller_id, uid=current_user.id)
        else:
            # insert new
            app.db.execute("""
                INSERT INTO SellerReviews (seller_id, user_id, rating, comment, date_reviewed)
                VALUES (:sid, :uid, :rating, :comment, NOW())
            """, sid=seller_id, uid=current_user.id,
               rating=rating, comment=comment or None)

        flash('Seller review saved!', 'success')
    except Exception as e:
        app.logger.exception("Error saving seller review")
        flash(f"Could not save seller review: {e}", "error")

    return redirect(url_for('users.public_profile', user_id=seller_id))

@bp.route('/user/<int:seller_id>/review/delete', methods=['POST'])
@login_required
def delete_seller_review(seller_id):
    """Delete the current user's review for a seller."""
    app.db.execute("""
        DELETE FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)

    flash('Your seller review was removed.', 'success')
    return redirect(url_for('users.public_profile', user_id=seller_id))



@bp.route('/my_reviews')
@login_required
def my_reviews():
    """Show both product reviews and seller reviews written by the current user."""
    db = app.db

    combined_reviews = []

    # -------- product reviews by this user --------
    product_rows = list(db.execute("""
        SELECT r.review_id,
               r.product_id,
               p.name,
               r.rating,
               r.comment,
               r.date_reviewed
        FROM Reviews r
        JOIN Products p ON p.id = r.product_id
        WHERE r.user_id = :uid
        ORDER BY r.date_reviewed DESC
    """, uid=current_user.id))

    for r in product_rows:
        combined_reviews.append({
            'kind': 'product',
            'rating': int(r[3]),
            'comment': r[4],
            'date_reviewed': r[5],
            'product_id': r[1],
            'product_name': r[2],
            'seller_id': None,
            'seller_name': None,
        })

    # -------- seller reviews by this user --------
    seller_rows = list(db.execute("""
        SELECT sr.id,
               sr.seller_id,
               u.firstname,
               u.lastname,
               sr.rating,
               sr.comment,
               sr.date_reviewed
        FROM SellerReviews sr
        JOIN Users u ON u.id = sr.seller_id
        WHERE sr.user_id = :uid
        ORDER BY sr.date_reviewed DESC
    """, uid=current_user.id))

    for r in seller_rows:
        combined_reviews.append({
            'kind': 'seller',
            'rating': int(r[4]),
            'comment': r[5],
            'date_reviewed': r[6],
            'product_id': None,
            'product_name': None,
            'seller_id': r[1],
            'seller_name': f"{r[2]} {r[3]}",
        })

    # -------- sort together: newest first --------
    combined_reviews.sort(key=lambda item: item['date_reviewed'], reverse=True)

    return render_template('my_reviews.html', reviews=combined_reviews)



@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))