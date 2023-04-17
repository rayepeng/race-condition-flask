# flask 条件竞争漏洞演示

起因是看到了p牛的这篇文章：https://mp.weixin.qq.com/s/9f5Hxoyw5ne8IcYx4uwwvQ

于是索性来探究下flask中如何对抗条件竞争漏洞，后续也会对比下nodejs、go等各种语言

## 实现

数据模型如下：

**用户表**

```python
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(256), unique=True, nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    money = db.Column(db.Integer, default=0)
```

**提现表**

```python
class WithdrawLog(db.Model):
    __tablename__ = 'withdraw_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_time = db.Column(db.DateTime, default=datetime.utcnow)
```

用户每提现一次，就会在提现的表上有一条记录，转账的应用会根据提现表的记录来转账

因此目的就是在只有10元的基础上，一次性增加多条10元的提现记录

**表单**

```python
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
```

## Withdraw 实现1

```python
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
```

这种情况下是肯定会遇到条件竞争漏洞的


## 悲观锁

```python
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
```

问题是这个，实测这里防不住条件竞争漏洞


## 其余测试

参见 `mysql_lock_test` 测试



## TODO

A 转账给 B 验证


这篇文章稍微讲解了下flask 条件竞争漏洞的成因
https://www.makeuseof.com/race-condition-vulnerability/

CPU在每个进程间依次轮转
![](https://static1.makeuseofimages.com/wordpress/wp-content/uploads/2022/11/round-robin-algorithm-diagram-drawing.jpg?q=50&fit=crop&w=1500&dpr=1.5)


这里是官方文档
https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/ 

