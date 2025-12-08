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
    """Show the logged-in user's purchase history."""
    purchases = Purchase.history_for_user(current_user.id)
    return render_template('user_purchases.html', purchases=purchases)

@bp.route('/api/user_purchases/<int:user_id>')
def get_user_purchases(user_id):
    """API endpoint to get user purchases with product details"""
    # TEMPORARY MOCK DATA FOR DEMO
    import datetime
    
    # Different mock data based on user_id for demo variety
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