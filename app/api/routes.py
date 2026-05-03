import json
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from app.api import api_bp
from app.extensions import db
from app.models import KeyPair, WatermarkRecord
from app.core.watermark_engine import embed_image, verify_image
from app.utils.helpers import allowed_file, save_upload


@api_bp.route("/embed", methods=["POST"])
@login_required
def api_embed():
    """API: 嵌入水印"""
    file = request.files.get("image")
    watermark_text = request.form.get("watermark_text", "").strip()
    alpha = float(request.form.get("alpha", 0.35))
    key_pair_id = request.form.get("key_pair_id", type=int)

    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "请上传有效图片"}), 400

    if not watermark_text or len(watermark_text) > 64:
        return jsonify({"success": False, "error": "水印文本1-64字符"}), 400

    kp = KeyPair.query.get(key_pair_id) if key_pair_id else KeyPair.query.first()
    if not kp:
        return jsonify({"success": False, "error": "无可用密钥对"}), 400

    upload_path = save_upload(file, current_app.config["UPLOAD_FOLDER"])
    if not upload_path:
        return jsonify({"success": False, "error": "文件保存失败"}), 500

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
            image_hash=result["image_hash"],
            embed_params=json.dumps({"alpha": alpha}),
        )
        db.session.add(record)
        db.session.commit()
        result["record_id"] = record.id

    return jsonify(result)


@api_bp.route("/verify", methods=["POST"])
@login_required
def api_verify():
    """API: 验证水印"""
    file = request.files.get("image")
    rsa_priv = request.form.get("rsa_private_key", "").strip()
    sm2_pub = request.form.get("sm2_public_key", "").strip()
    alpha = float(request.form.get("alpha", 0.35))

    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "请上传有效图片"}), 400

    if not rsa_priv:
        kp = KeyPair.query.filter_by(user_id=current_user.id).first()
        if kp:
            rsa_priv = kp.rsa_private_key_encrypted
            if not sm2_pub:
                sm2_pub = kp.sm2_public_key

    if not rsa_priv:
        return jsonify({"success": False, "error": "请提供RSA私钥"}), 400

    upload_path = save_upload(file, current_app.config["UPLOAD_FOLDER"])
    if not upload_path:
        return jsonify({"success": False, "error": "文件保存失败"}), 500

    result = verify_image(
        image_path=upload_path,
        rsa_private_key=rsa_priv,
        sm2_public_key=sm2_pub,
        alpha=alpha,
    )

    return jsonify(result)


@api_bp.route("/keys", methods=["GET"])
@login_required
def api_list_keys():
    """API: 列出公钥"""
    keys = KeyPair.query.all()
    return jsonify([{
        "id": k.id,
        "sm2_public_key": k.sm2_public_key,
        "rsa_public_key": k.rsa_public_key,
        "created_at": k.created_at.isoformat(),
    } for k in keys])


@api_bp.route("/records", methods=["GET"])
@login_required
def api_list_records():
    """API: 列出记录"""
    q = WatermarkRecord.query
    if not current_user.is_admin:
        q = q.filter_by(user_id=current_user.id)
    records = q.order_by(WatermarkRecord.created_at.desc()).limit(50).all()
    return jsonify([{
        "id": r.id,
        "watermark_text": r.watermark_text,
        "image_hash": r.image_hash,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
    } for r in records])
