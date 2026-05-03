"""Initialize database and create default admin account"""
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()

    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Admin created: admin / admin123")
    else:
        print("Admin account already exists")

    print("Database initialized")
