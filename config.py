import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _get_secret_key() -> str:
    """获取 SECRET_KEY：优先环境变量，否则自动生成并持久化"""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key

    key_file = BASE_DIR / "instance" / ".secret_key"
    try:
        if key_file.exists():
            return key_file.read_text().strip()
    except OSError:
        pass

    # 生成随机密钥并持久化
    key = secrets.token_hex(32)
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key)
    except OSError:
        pass
    return key


class Config:
    SECRET_KEY = _get_secret_key()
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'photoefas.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    OUTPUT_FOLDER = str(BASE_DIR / "outputs")
    KEY_FOLDER = str(BASE_DIR / "keys")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp"}


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
