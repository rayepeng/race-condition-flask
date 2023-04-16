# 测试 flask-sqlalchemy 的 with_for_update() 方法

# 1. 用 with_for_update() 方法获取用户记录
# 2. 检查用户余额是否足够
# 3. 如果足够，扣除余额并提交事务
# 4. 如果不足，撤回事务以释放锁
# 5. 如果发生异常，撤回事务以释放锁

from flask_sqlalchemy import SQLAlchemy
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://myuser:mypassword@localhost/mydb?charset=utf8mb4'
db = SQLAlchemy(app)

# 用户模型
class NewUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    money = db.Column(db.Integer, default=0)

    def set_username(self, username):
        self.username = username

    def set_money(self, money):
        self.money = money


import threading
import time
from time import sleep

def withdraw():
    # 获取test用户
    with app.app_context():
        # 开始时间
        start = time.time()

        # 不使用锁
        user = NewUser.query.filter_by(username='test').first()
        # 检查余额是否足够
        if user.money < 10:
            print('余额不足')
            return
        # 扣除余额
        user.money -= 10
        # 打印线程 + 当前余额
        print(threading.current_thread().name, user.money)
        sleep(1)
        
        db.session.commit()
        end = time.time()
        # 打印线程名 + 耗时
        print(threading.current_thread().name, '耗时：', end - start)

# 带锁的withdraw
def withdraw_with_lock():
    # 获取test用户
    with app.app_context():
        # 开始时间
        start = time.time()

        # 使用锁
        user = NewUser.query.filter_by(username='test').with_for_update().first()
        # 检查余额是否足够
        if user.money < 10:
            print('余额不足')
            return
        # 扣除余额
        user.money -= 10
        # 打印线程 + 当前余额
        print(threading.current_thread().name, user.money)
        sleep(1)
        db.session.commit()
        end = time.time()
        # 打印线程名 + 耗时
        print(threading.current_thread().name, '耗时：', end - start)




# 多线程
if __name__ == '__main__':
    # 20个线程，等待执行结束，加入列表
    # 统计执行时间
    start = time.time()

    threads = []
    for i in range(20):
        t = threading.Thread(target=withdraw)
        t.start()
        threads.append(t)
    
    # 等待所有线程执行完毕
    for t in threads:
        t.join()

    end = time.time()
    print('耗时：', end - start)
    
