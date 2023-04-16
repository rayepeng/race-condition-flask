from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime
from flask_bootstrap import Bootstrap
from flask import render_template, flash, redirect, url_for, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from flask_migrate import Migrate
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.exc import IntegrityError
from flask_admin import Admin, AdminIndexView, expose
import time
app = Flask(__name__)
Bootstrap(app)  # Bootsrap 装饰一下
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://myuser:mypassword@localhost/mydb?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secretkey'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = SQLAlchemy(app)

# 运行 flask db init
# flask db migrate -m "Initial migration"
# flask db upgrade
migrate = Migrate(app, db) 

# 用户
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    money = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return '<User %r>' % self.username

# 提现
class WithdrawLog(db.Model):
    __tablename__ = 'withdraw_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_time = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<WithdrawLog %r>' % self.id

# 编写WithDrawForm
class WithDrawForm(FlaskForm):
    amount = StringField('Amount', validators=[DataRequired()])
    submit = SubmitField('Withdraw')

    # 自定义验证器
    def validate_amount(self, amount):
        if not amount.data.isdigit():
            raise ValidationError('Amount must be a number')
        if int(amount.data) <= 0:
            raise ValidationError('Amount must be greater than 0')
        if int(amount.data) > current_user.money:
            raise ValidationError('Insufficient funds')

# 注册表单
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 自定义 AdminIndexView，添加身份验证
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    @login_required
    def index(self):
        return super(MyAdminIndexView, self).index()

# 自定义 ModelView，添加身份验证
class MyModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

    def on_model_change(self, form, model, is_created):
        if is_created or form.password.data != '':
            model.set_password(form.password.data)
        super(MyModelView, self).on_model_change(form, model, is_created)
    
admin = Admin(app, name='My App Admin', template_mode='bootstrap4', index_view=MyAdminIndexView())
admin.add_view(MyModelView(User, db.session))
admin.add_view(MyModelView(WithdrawLog, db.session))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('admin')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            print(f"find user {user}")
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

# 实现注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Account created for {}!'.format(form.username.data))
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/withdraw1', methods=['GET','POST'])
@login_required
def withdraw1():
    form = WithDrawForm()
    # 如果POST且验证通过
    if form.validate_on_submit():
        amount = int(form.amount.data)
        current_user.money -= amount
        db.session.add(WithdrawLog(user_id=current_user.id, amount=amount))
        db.session.commit()
        flash('Withdrawal successful')
        return redirect(url_for('index'))
    return render_template('withdraw.html', form=form)


@app.route('/withdraw2', methods=['GET','POST'])
@login_required
def withdraw2():
    form = WithDrawForm()
    # 转账增加事务
    if form.validate_on_submit():
        amount = int(form.amount.data)
        try:
            current_user.money -= amount
            db.session.add(WithdrawLog(user_id=current_user.id, amount=amount))
            db.session.commit()
            flash('Withdrawal successful')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('Withdrawal failed')
            return redirect(url_for('index'))
    return render_template('withdraw.html', form=form)


@app.route('/withdraw3', methods=['GET','POST'])
@login_required
def withdraw3():
    form = WithDrawForm()
    # 加悲观锁
    if form.validate_on_submit():
        amount = int(form.amount.data)
        try:
            # Lock the user row
            locked_user = db.session.query(User).with_for_update().filter_by(id=current_user.id).first()
            if locked_user.money >= amount:
                locked_user.money -= amount
                db.session.add(WithdrawLog(user_id=current_user.id, amount=amount))
                db.session.commit()
                flash('Withdrawal successful')
                return redirect(url_for('index'))
            else:
                db.session.rollback()
                flash('Insufficient funds')
                return render_template('withdraw.html', form=form)
        except Exception as e:
            db.session.rollback()
            flash('Withdrawal failed')
            return render_template('withdraw.html', form=form)
    return render_template('withdraw.html', form=form)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/index')
def index():
    return "hello world"

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=6001)

# flask shell
# >>> from app import db
# >>> from app import User
# >>> new_user =User(username='rayepeng', email='rayepeng@tencent.com')
# >>> new_user.set_password('123456')
# >>> db.session.add(new_user)
# >>> db.session.commit()