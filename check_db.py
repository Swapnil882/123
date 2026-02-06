from app import create_app
from app.models import User
from app.extensions import db

app = create_app()
app.app_context().push()

users = User.query.all()
print(f'Users in DB: {len(users)}')
for u in users:
    print(f'{u.username}, {u.email}')
