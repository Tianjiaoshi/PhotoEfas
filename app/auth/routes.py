from datetime import datetime
from urllib.parse import urlparse
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db
from app.models import User, InviteCode


def _is_safe_url(target: str) -> bool:
    """验证重定向目标是否为安全的站内URL"""
    if not target:
        return False
    parsed = urlparse(target)
    # 仅允许相对路径（无 scheme、无 netloc）
    return not parsed.scheme and not parsed.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard" if current_user.is_admin else "user.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            if not _is_safe_url(next_page):
                next_page = None
            if user.is_admin:
                return redirect(next_page or url_for("admin.dashboard"))
            return redirect(next_page or url_for("user.dashboard"))

        flash("用户名或密码错误", "error")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        invite_code = request.form.get("invite_code", "").strip()

        if not username or not password:
            flash("用户名和密码不能为空", "error")
        elif len(password) < 6:
            flash("密码长度至少6位", "error")
        elif password != confirm:
            flash("两次密码不一致", "error")
        elif not invite_code:
            flash("请输入邀请码", "error")
        elif User.query.filter_by(username=username).first():
            flash("用户名已存在", "error")
        else:
            # 验证邀请码
            code = InviteCode.query.filter_by(code=invite_code, is_active=True).first()
            if not code or not code.is_valid:
                flash("邀请码无效或已过期", "error")
            else:
                user = User(username=username, role="user")
                user.set_password(password)
                db.session.add(user)
                db.session.flush()  # 获取user.id

                # 标记邀请码已使用
                code.use_count += 1
                code.used_by = user.id
                code.used_at = datetime.utcnow()
                if code.use_count >= code.max_uses:
                    code.is_active = False

                db.session.commit()
                flash("注册成功，请登录", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))
