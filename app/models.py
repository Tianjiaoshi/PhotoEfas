import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    key_pairs = db.relationship("KeyPair", backref="owner", lazy=True)
    records = db.relationship("WatermarkRecord", backref="owner", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    used_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    max_uses = db.Column(db.Integer, nullable=False, default=1)
    use_count = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by], backref="created_codes")
    user = db.relationship("User", foreign_keys=[used_by], backref="used_codes")

    @staticmethod
    def generate_code(length=32):
        return secrets.token_hex(length // 2)

    @property
    def is_valid(self):
        return self.is_active and self.use_count < self.max_uses


class KeyPair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    key_type = db.Column(db.String(20), nullable=False, default="sm2_rsa")
    sm2_public_key = db.Column(db.Text, nullable=False)
    sm2_private_key_encrypted = db.Column(db.Text, nullable=False)
    rsa_public_key = db.Column(db.Text, nullable=False)
    rsa_private_key_encrypted = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatermarkRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    original_image_path = db.Column(db.String(500), nullable=False)
    watermarked_image_path = db.Column(db.String(500))
    watermark_text = db.Column(db.String(200), nullable=False)
    sm2_signature = db.Column(db.Text)
    image_hash = db.Column(db.String(64))
    embed_params = db.Column(db.Text)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
