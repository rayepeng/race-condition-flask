from app import User

new_user = User(username='raye', email='raye@tt.com')

new_user.set_password('123456')

db.session.add(new_user)
db.session.commit()