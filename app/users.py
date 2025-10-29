from flask import render_template, redirect, url_for, flash, request
from werkzeug.urls import url_parse
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
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
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(),
                                       EqualTo('password')])
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
                         form.lastname.data):
            flash('Congratulations, you are now a registered user!')
            return redirect(url_for('users.login'))
    return render_template('register.html', title='Register', form=form)

@bp.route('/user_purchases')
def user_purchases_page():
    """Serve the user purchases page"""
    return render_template('user_purchases.html')

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

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))
