import os
import json
from pathlib import Path
from flask import render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from functools import wraps
from app.admin import admin_bp
from app.extensions import db
from app.models import User, KeyPair, WatermarkRecord, InviteCode
from app.core.crypto import generate_sm2_keypair, generate_rsa_keypair
from app.core.watermark_engine import embed_image, verify_image as do_verify_image
from app.utils.helpers import allowed_file, save_upload


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash("需要管理员权限", "error")
            return redirect(url_for("user.dashboard"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@admin_required
def dashboard():
    from app.utils.cleanup import get_folder_size, format_size
    total_records = WatermarkRecord.query.count()
    total_users = User.query.filter_by(role="user").count()
    total_keys = KeyPair.query.count()
    recent_records = WatermarkRecord.query.order_by(WatermarkRecord.created_at.desc()).limit(10).all()
    upload_size = format_size(get_folder_size(current_app.config["UPLOAD_FOLDER"]))
    output_size = format_size(get_folder_size(current_app.config["OUTPUT_FOLDER"]))
    return render_template("admin/dashboard.html",
                           total_records=total_records,
                           total_users=total_users,
                           total_keys=total_keys,
                           recent_records=recent_records,
                           upload_size=upload_size,
                           output_size=output_size)


@admin_bp.route("/keys")
@admin_required
def key_management():
    key_pairs = KeyPair.query.order_by(KeyPair.created_at.desc()).all()
    return render_template("admin/keys.html", key_pairs=key_pairs)


@admin_bp.route("/keys/generate", methods=["POST"])
@admin_required
def generate_keys():
    sm2_priv, sm2_pub = generate_sm2_keypair()
    rsa_priv, rsa_pub = generate_rsa_keypair(2048)

    kp = KeyPair(
        user_id=current_user.id,
        sm2_public_key=sm2_pub,
        sm2_private_key_encrypted=sm2_priv,  # 生产环境应加密存储
        rsa_public_key=rsa_pub,
        rsa_private_key_encrypted=rsa_priv,
    )
    db.session.add(kp)
    db.session.commit()

    flash("密钥对已生成", "success")
    return redirect(url_for("admin.key_management"))


@admin_bp.route("/keys/<int:key_id>/delete", methods=["POST"])
@admin_required
def delete_key(key_id):
    kp = KeyPair.query.get_or_404(key_id)
    db.session.delete(kp)
    db.session.commit()
    flash("密钥对已删除", "info")
    return redirect(url_for("admin.key_management"))


@admin_bp.route("/embed", methods=["GET", "POST"])
@admin_required
def embed_watermark():
    if request.method == "POST":
        file = request.files.get("image")
        watermark_text = request.form.get("watermark_text", "").strip()
        alpha = float(request.form.get("alpha", 0.35))
        key_pair_id = request.form.get("key_pair_id", type=int)

        if not file or not allowed_file(file.filename):
            flash("请上传有效的图片文件 (PNG/JPG/BMP)", "error")
            return redirect(request.url)

        if not watermark_text:
            flash("请输入水印文本", "error")
            return redirect(request.url)

        if len(watermark_text) > 64:
            flash("水印文本最长64字符", "error")
            return redirect(request.url)

        kp = KeyPair.query.get(key_pair_id) if key_pair_id else KeyPair.query.first()
        if not kp:
            flash("请先生成密钥对", "error")
            return redirect(url_for("admin.key_management"))

        # 保存上传文件
        upload_path = save_upload(file, current_app.config["UPLOAD_FOLDER"])
        if not upload_path:
            flash("文件保存失败", "error")
            return redirect(request.url)

        # 嵌入水印
        result = embed_image(
            image_path=upload_path,
            watermark_text=watermark_text,
            user_id=current_user.id,
            sm2_private_key=kp.sm2_private_key_encrypted,
            rsa_public_key=kp.rsa_public_key,
            output_dir=current_app.config["OUTPUT_FOLDER"],
            alpha=alpha,
        )

        if result["success"]:
            record = WatermarkRecord(
                user_id=current_user.id,
                original_image_path=upload_path,
                watermarked_image_path=result["watermarked_path"],
                watermark_text=watermark_text,
                sm2_signature="",
                image_hash=result["image_hash"],
                embed_params=json.dumps({
                    "alpha": alpha,
                    "key_pair_id": kp.id,
                    "redundancy": result.get("redundancy", 4),
                }),
            )
            db.session.add(record)
            db.session.commit()

            flash(f"水印嵌入成功！容量: {result['capacity']}比特", "success")
            return render_template("admin/embed.html",
                                   key_pairs=KeyPair.query.all(),
                                   result=result,
                                   record=record,
                                   alpha=alpha)
        else:
            flash(f"嵌入失败: {result['error']}", "error")

    return render_template("admin/embed.html", key_pairs=KeyPair.query.all())


@admin_bp.route("/verify", methods=["GET", "POST"])
@admin_required
def verify_image():
    if request.method == "POST":
        file = request.files.get("image")
        key_pair_id = request.form.get("key_pair_id", type=int)
        alpha = float(request.form.get("alpha", 0.35))

        if not file or not allowed_file(file.filename):
            flash("请上传有效的图片文件", "error")
            return redirect(request.url)

        kp = KeyPair.query.get(key_pair_id) if key_pair_id else KeyPair.query.first()
        if not kp:
            flash("请先生成密钥对", "error")
            return redirect(url_for("admin.key_management"))

        upload_path = save_upload(file, current_app.config["UPLOAD_FOLDER"])
        if not upload_path:
            flash("文件保存失败", "error")
            return redirect(request.url)

        result = do_verify_image(
            image_path=upload_path,
            rsa_private_key=kp.rsa_private_key_encrypted,
            sm2_public_key=kp.sm2_public_key,
            alpha=alpha,
        )

        return render_template("admin/verify.html",
                               key_pairs=KeyPair.query.all(),
                               result=result)

    return render_template("admin/verify.html", key_pairs=KeyPair.query.all())


@admin_bp.route("/records")
@admin_required
def records():
    page = request.args.get("page", 1, type=int)
    pagination = WatermarkRecord.query.order_by(
        WatermarkRecord.created_at.desc()
    ).paginate(page=page, per_page=20)
    return render_template("admin/records.html", pagination=pagination)


@admin_bp.route("/download/<int:record_id>")
@admin_required
def download(record_id):
    record = WatermarkRecord.query.get_or_404(record_id)
    file_path = record.watermarked_image_path
    if not file_path:
        flash("文件不存在", "error")
        return redirect(url_for("admin.records"))

    # 防止路径遍历：确保文件在允许的目录内
    real_path = os.path.realpath(file_path)
    allowed_dirs = [
        os.path.realpath(current_app.config["OUTPUT_FOLDER"]),
        os.path.realpath(current_app.config["UPLOAD_FOLDER"]),
    ]
    if not any(real_path.startswith(d) for d in allowed_dirs):
        flash("文件路径不合法", "error")
        return redirect(url_for("admin.records"))

    if os.path.exists(real_path):
        return send_file(real_path, as_attachment=True)
    flash("文件不存在", "error")
    return redirect(url_for("admin.records"))


@admin_bp.route("/records/<int:record_id>/delete", methods=["POST"])
@admin_required
def delete_record(record_id):
    record = WatermarkRecord.query.get_or_404(record_id)
    # 删除关联的图片文件
    for path in [record.original_image_path, record.watermarked_image_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    db.session.delete(record)
    db.session.commit()
    flash("记录已删除", "info")
    return redirect(request.referrer or url_for("admin.records"))


@admin_bp.route("/records/clear", methods=["POST"])
@admin_required
def clear_all_records():
    records = WatermarkRecord.query.all()
    count = 0
    for record in records:
        for path in [record.original_image_path, record.watermarked_image_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        db.session.delete(record)
        count += 1
    db.session.commit()
    flash(f"已清空 {count} 条记录及关联文件", "info")
    return redirect(url_for("admin.records"))


@admin_bp.route("/cleanup", methods=["POST"])
@admin_required
def cleanup_files():
    """清理孤立文件和过期文件"""
    from app.utils.cleanup import cleanup_orphan_files, cleanup_old_files, get_folder_size, format_size
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    output_dir = current_app.config["OUTPUT_FOLDER"]

    orphan_stats = cleanup_orphan_files(upload_dir, output_dir, db, WatermarkRecord)
    old_stats = cleanup_old_files(upload_dir, output_dir, max_age_hours=24)

    total_deleted = orphan_stats["deleted_uploads"] + orphan_stats["deleted_outputs"] + old_stats["deleted"]
    upload_size = format_size(get_folder_size(upload_dir))
    output_size = format_size(get_folder_size(output_dir))

    flash(f"清理完成: 删除 {total_deleted} 个文件 | uploads: {upload_size} | outputs: {output_size}", "info")
    return redirect(url_for("admin.dashboard"))


# ============ 邀请码管理 ============

@admin_bp.route("/invite-codes")
@admin_required
def invite_codes():
    codes = InviteCode.query.order_by(InviteCode.created_at.desc()).all()
    return render_template("admin/invite_codes.html", codes=codes)


@admin_bp.route("/invite-codes/generate", methods=["POST"])
@admin_required
def generate_invite_code():
    count = request.form.get("count", 1, type=int)
    max_uses = request.form.get("max_uses", 1, type=int)
    count = min(max(count, 1), 50)
    max_uses = min(max(max_uses, 1), 100)

    new_codes = []
    for _ in range(count):
        code = InviteCode(
            code=InviteCode.generate_code(32),
            created_by=current_user.id,
            max_uses=max_uses,
        )
        db.session.add(code)
        new_codes.append(code)

    db.session.commit()
    flash(f"已生成 {count} 个邀请码（每个可用 {max_uses} 次）", "success")
    return redirect(url_for("admin.invite_codes"))


@admin_bp.route("/invite-codes/<int:code_id>/toggle", methods=["POST"])
@admin_required
def toggle_invite_code(code_id):
    code = InviteCode.query.get_or_404(code_id)
    code.is_active = not code.is_active
    db.session.commit()
    status = "启用" if code.is_active else "禁用"
    flash(f"邀请码已{status}", "info")
    return redirect(url_for("admin.invite_codes"))


@admin_bp.route("/invite-codes/<int:code_id>/delete", methods=["POST"])
@admin_required
def delete_invite_code(code_id):
    code = InviteCode.query.get_or_404(code_id)
    db.session.delete(code)
    db.session.commit()
    flash("邀请码已删除", "info")
    return redirect(url_for("admin.invite_codes"))
