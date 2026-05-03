import os
import json
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.user import user_bp
from app.extensions import db
from app.models import KeyPair, WatermarkRecord
from app.core.watermark_engine import verify_image
from app.utils.helpers import allowed_file, save_upload


@user_bp.route("/")
@login_required
def dashboard():
    records = WatermarkRecord.query.filter_by(user_id=current_user.id).order_by(
        WatermarkRecord.created_at.desc()
    ).limit(10).all()
    return render_template("user/dashboard.html", records=records)


@user_bp.route("/upload-key", methods=["GET", "POST"])
@login_required
def upload_key():
    if request.method == "POST":
        sm2_pub = request.form.get("sm2_public_key", "").strip()
        rsa_priv = request.form.get("rsa_private_key", "").strip()

        if not rsa_priv:
            flash("请提供RSA私钥", "error")
            return redirect(request.url)

        # 检查是否已有密钥
        existing = KeyPair.query.filter_by(user_id=current_user.id).first()
        if existing:
            existing.sm2_public_key = sm2_pub or existing.sm2_public_key
            existing.rsa_private_key_encrypted = rsa_priv
            flash("密钥已更新", "success")
        else:
            kp = KeyPair(
                user_id=current_user.id,
                sm2_public_key=sm2_pub or "",
                sm2_private_key_encrypted="",
                rsa_public_key="",
                rsa_private_key_encrypted=rsa_priv,
            )
            db.session.add(kp)
            flash("密钥已保存", "success")

        db.session.commit()
        return redirect(url_for("user.dashboard"))

    existing = KeyPair.query.filter_by(user_id=current_user.id).first()
    return render_template("user/upload_key.html", existing_key=existing)


@user_bp.route("/verify", methods=["GET", "POST"])
@login_required
def verify():
    if request.method == "POST":
        file = request.files.get("image")
        rsa_priv = request.form.get("rsa_private_key", "").strip()
        sm2_pub = request.form.get("sm2_public_key", "").strip()
        alpha = float(request.form.get("alpha", 0.35))

        # 如果用户没提供密钥，从数据库读取
        if not rsa_priv:
            kp = KeyPair.query.filter_by(user_id=current_user.id).first()
            if kp:
                rsa_priv = kp.rsa_private_key_encrypted
                if not sm2_pub:
                    sm2_pub = kp.sm2_public_key

        if not file or not allowed_file(file.filename):
            flash("请上传有效的图片文件", "error")
            return redirect(request.url)

        if not rsa_priv:
            flash("请提供RSA私钥（在'我的密钥'页面上传）", "error")
            return redirect(request.url)

        upload_path = save_upload(file, current_app.config["UPLOAD_FOLDER"])
        if not upload_path:
            flash("文件保存失败", "error")
            return redirect(request.url)

        result = verify_image(
            image_path=upload_path,
            rsa_private_key=rsa_priv,
            sm2_public_key=sm2_pub,
            alpha=alpha,
        )

        return render_template("user/verify.html", result=result)

    return render_template("user/verify.html")


@user_bp.route("/records")
@login_required
def records():
    page = request.args.get("page", 1, type=int)
    pagination = WatermarkRecord.query.filter_by(user_id=current_user.id).order_by(
        WatermarkRecord.created_at.desc()
    ).paginate(page=page, per_page=20)
    return render_template("user/records.html", pagination=pagination)
