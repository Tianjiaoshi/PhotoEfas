import os
import atexit
from flask import Flask, redirect, url_for
from flask_login import current_user
from config import Config
from app.extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.user.routes import user_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.template_filter("from_json")
    def from_json_filter(s):
        import json
        try:
            return json.loads(s) if s else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("user.dashboard"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        from app import models
        db.create_all()

        # 启动时清理超过24小时的孤立文件
        _run_startup_cleanup(app)

        # Linux: 启动定时清理（每6小时）
        _start_scheduler(app)

    return app


def _run_startup_cleanup(app):
    """启动时清理孤立文件（uploads/outputs中无数据库记录的文件）"""
    from app.utils.cleanup import cleanup_old_files, format_size, get_folder_size
    upload_dir = app.config["UPLOAD_FOLDER"]
    output_dir = app.config["OUTPUT_FOLDER"]

    # 清理超过24小时的文件
    stats = cleanup_old_files(upload_dir, output_dir, max_age_hours=24)
    if stats["deleted"] > 0:
        app.logger.info(
            f"Startup cleanup: deleted {stats['deleted']} old files, "
            f"uploads={format_size(get_folder_size(upload_dir))}, "
            f"outputs={format_size(get_folder_size(output_dir))}"
        )


def _start_scheduler(app):
    """启动定时清理调度器（后台线程，每6小时执行一次）"""
    import threading

    def _scheduled_cleanup():
        with app.app_context():
            from app.utils.cleanup import cleanup_old_files
            stats = cleanup_old_files(
                app.config["UPLOAD_FOLDER"],
                app.config["OUTPUT_FOLDER"],
                max_age_hours=24,
            )
            if stats["deleted"] > 0:
                app.logger.info(f"Scheduled cleanup: deleted {stats['deleted']} old files")

    def _run_periodically(interval_hours):
        import time
        while True:
            time.sleep(interval_hours * 3600)
            try:
                _scheduled_cleanup()
            except Exception as e:
                app.logger.error(f"Scheduled cleanup error: {e}")

    t = threading.Thread(target=_run_periodically, args=(6,), daemon=True)
    t.start()
