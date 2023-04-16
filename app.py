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
# from sqlalchemy.sql.expression import with_for_update
from flask_admin import Admin, AdminIndexView, expose
from sqlalchemy import text

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
            return redirect(url_for('withdraw2'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/withdraw1', methods=['GET','POST'])
@login_required
def withdraw1():
    if request.method == 'POST':
        amount = int(request.form['amount'])
        if current_user.money >= amount:
            current_user.money -= amount
            db.session.add(WithdrawLog(user_id=current_user.id, amount=amount))
            db.session.commit()
            flash('Withdrawal successful')
            return redirect(url_for('index'))
        else:
            flash('Insufficient funds')
    return render_template('withdraw.html')


@app.route('/withdraw2', methods=['GET','POST'])
@login_required
def withdraw2():
    if request.method == 'POST':
        amount = int(request.form['amount'])
        if current_user.money >= amount:
            with db.session.begin_nested():
                # 增加原子操作
                try:
                    current_user.money -= amount
                    db.session.add(WithdrawLog(user_id=current_user.id, amount=amount))
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash('An error occurred during withdrawal. Please try again.')
                    return render_template('withdraw.html')
            flash('Withdrawal successful')
            return redirect(url_for('index'))
        else:
            flash('Insufficient funds')
    return render_template('withdraw.html')

@app.route('/withdraw3', methods=['GET','POST'])
@login_required
def withdraw3():
    if request.method == 'POST':
        amount = int(request.form['amount'])

        # 开始一个新的事务，这里无法开启新事物只能开启嵌套事物
        with db.session.begin_nested():
            # 使用悲观锁获取用户记录
            locked_user = db.session.query(User).filter(User.id==current_user.id).with_for_update().first()

            if locked_user.money >= amount:
                locked_user.money -= amount
                db.session.add(WithdrawLog(user_id=locked_user.id, amount=amount))
                db.session.commit()
                flash('Withdrawal successful')
                return redirect(url_for('index'))
            else:
                # 撤回事务以释放锁
                db.session.rollback()
                flash('Insufficient funds')

    return render_template('withdraw.html')

@app.route('/withdraw4', methods=['GET', 'POST'])
@login_required
def withdraw4():
    if request.method == 'POST':
        amount = int(request.form['amount'])

        # 获取当前用户
        user = User.query.get(current_user.id)
        if user.money >= amount:
            try:
                # Lock the user row
                locked_user = db.session.query(User).with_for_update().filter_by(id=user.id).first()
                if locked_user.money >= amount:
                    locked_user.money -= amount
                    db.session.add(WithdrawLog(user_id=user.id, amount=amount))
                    db.session.commit()
                    flash('Withdrawal successful')
                    return redirect(url_for('index'))
                else:
                    db.session.rollback()
                    flash('Insufficient funds')
                    return render_template('withdraw.html')
            except IntegrityError:
                db.session.rollback()
    return render_template('withdraw.html')


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