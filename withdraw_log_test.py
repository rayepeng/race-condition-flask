from flask_sqlalchemy import SQLAlchemy
from flask import Flask

import threading
import time

# datetime
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://myuser:mypassword@localhost/mydb?charset=utf8mb4'
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    money = db.Column(db.Integer, default=0)

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


def withdraw_lock(amount):
    with app.app_context():
        start = time.time()
        user = User.query.filter_by(username='rayepeng').with_for_update().first()
        # 检查余额是否足够
        if user.money < amount:
            print('余额不足')
            return
        # 扣除余额
        user.money -= amount
        # 打印线程 + 当前余额
        print(threading.current_thread().name, user.money)
        # 写入提现记录
        withdraw_log = WithdrawLog()
        withdraw_log.user_id = user.id
        withdraw_log.amount = 10
        db.session.add(withdraw_log)
        db.session.commit()
        end = time.time()
        # 打印线程名 + 耗时
        print(threading.current_thread().name, '耗时：', end - start)


# 不加锁的版本
def withdraw(amount):
    with app.app_context():
        start = time.time()
        user = User.query.filter_by(username='rayepeng').first()
        # 检查余额是否足够
        if user.money < amount:
            print('余额不足')
            return
        # 扣除余额
        user.money -= amount
        # 打印线程 + 当前余额
        print(threading.current_thread().name, user.money)
        # 写入提现记录
        withdraw_log = WithdrawLog()
        withdraw_log.user_id = user.id
        withdraw_log.amount = 10
        db.session.add(withdraw_log)
        db.session.commit()
        end = time.time()
        # 打印线程名 + 耗时
        print(threading.current_thread().name, '耗时：', end - start)



# 20个线程测试
threads = []
for i in range(1000):
    t = threading.Thread(target=withdraw_lock, args=(10,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()


# 修改为线程池测试
# from concurrent.futures import ThreadPoolExecutor
#
# pool = ThreadPoolExecutor(20)
# for i in range(20):
#     pool.submit(withdraw, 10)




# Path: withdraw_log_test.py
# Compare this snippet from mysql_lock_test.py:


