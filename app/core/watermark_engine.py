"""水印编排器 - 整合DCT水印、加密、纠错的完整流程

冗余策略：
- 重复编码: 3x (每字节重复3次，纠错1位错误)
- 嵌入冗余: 动态计算，根据图像容量自动选择（1-4x）
- 总容量需求 = 原始密文字节数 × 8 × 重复次数 × 嵌入冗余
"""
import os
import hashlib
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

from app.core.dct_watermark import (
    embed_with_redundancy,
    extract_with_redundancy,
    get_capacity,
)
from app.core.bch_codec import encode_payload, decode_payload
from app.core.crypto import (
    sm2_sign,
    sm2_verify,
    rsa_encrypt,
    rsa_decrypt,
    build_payload,
    parse_payload,
)

# 重复编码倍数
REPETITION_FACTOR = 3


def compute_image_hash(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_image_data_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _calculate_embed_redundancy(image_shape: tuple, encoded_bit_count: int) -> int:
    """计算可用的嵌入冗余倍数

    Args:
        image_shape: 图像尺寸 (H, W)
        encoded_bit_count: 编码后的比特数

    Returns:
        嵌入冗余倍数（1-4）
    """
    h, w = image_shape[:2]
    blocks = (h // 8) * (w // 8)
    available_slots = blocks * 4  # 每块4个中频位

    max_redundancy = available_slots // encoded_bit_count
    return min(4, max(1, max_redundancy))


def embed_image(
    image_path: str,
    watermark_text: str,
    user_id: int,
    sm2_private_key: str,
    rsa_public_key: str,
    output_dir: str,
    alpha: float = 0.35,
) -> dict:
    """完整水印嵌入流程"""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"success": False, "error": "无法读取图片"}

        h, w = img.shape[:2]

        # 计算图片哈希
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_hash = compute_image_data_hash(image_bytes)

        # SM2签名图片哈希
        sm2_sig = sm2_sign(sm2_private_key, bytes.fromhex(image_hash))

        # 构建payload并RSA加密
        payload = build_payload(watermark_text, user_id, image_hash, sm2_sig)
        ciphertext = rsa_encrypt(rsa_public_key, payload)

        # 重复编码
        encoded, original_bit_count = encode_payload(ciphertext)

        # 转比特流
        bit_stream = []
        for byte in encoded:
            for i in range(7, -1, -1):
                bit_stream.append((byte >> i) & 1)

        # 计算嵌入冗余
        redundancy = _calculate_embed_redundancy((h, w), len(bit_stream))
        total_dct_slots_needed = len(bit_stream) * redundancy

        h_blocks = h // 8
        w_blocks = w // 8
        total_slots = h_blocks * w_blocks * 4

        if total_dct_slots_needed > total_slots:
            return {
                "success": False,
                "error": f"图片太小({w}x{h})，需要{total_dct_slots_needed}个DCT位槽，仅有{total_slots}个。建议使用更大的图片。",
            }

        # BGR -> YCrCb -> 嵌入
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        y_channel = ycrcb[:, :, 0]
        y_watermarked = embed_with_redundancy(y_channel, bit_stream, alpha=alpha, redundancy=redundancy)
        ycrcb[:, :, 0] = y_watermarked
        img_watermarked = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        # 保存 - 保持原格式（PNG无损，JPEG高质量）
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        src_ext = os.path.splitext(image_path)[1].lower()
        filename = f"wm_{timestamp}{src_ext}"
        output_path = str(Path(output_dir) / filename)
        if src_ext in ('.jpg', '.jpeg'):
            cv2.imwrite(output_path, img_watermarked, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            cv2.imwrite(output_path, img_watermarked)

        return {
            "success": True,
            "watermarked_path": output_path,
            "image_hash": image_hash,
            "capacity": total_slots,
            "payload_size": len(payload),
            "ciphertext_size": len(ciphertext),
            "encoded_size": len(encoded),
            "total_bits": len(bit_stream),
            "redundancy": redundancy,
            "dct_slots_used": total_dct_slots_needed,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_image(
    image_path: str,
    rsa_private_key: str,
    sm2_public_key: str,
    alpha: float = 0.35,
    redundancy: int = None,
) -> dict:
    """完整水印验证流程

    Args:
        image_path: 待验证图片路径
        rsa_private_key: RSA私钥（PEM）
        sm2_public_key: SM2公钥（hex）
        alpha: 嵌入强度（必须与嵌入时一致）
        redundancy: 嵌入冗余（必须与嵌入时一致）。None则自动检测。
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"valid": False, "error": "无法读取图片"}

        h, w = img.shape[:2]

        # 计算当前图片哈希
        with open(image_path, "rb") as f:
            current_hash = compute_image_data_hash(f.read())

        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        y_channel = ycrcb[:, :, 0]

        # RSA-2048 OAEP 固定输出256字节
        ciphertext_size = 256

        # 计算编码后数据量
        encoded_byte_count = ciphertext_size * REPETITION_FACTOR
        encoded_bit_count = encoded_byte_count * 8

        # 自动检测冗余（如果未指定）
        if redundancy is None:
            redundancy = _calculate_embed_redundancy((h, w), encoded_bit_count)

        # DCT提取
        extracted_bits = extract_with_redundancy(y_channel, encoded_bit_count, alpha=alpha, redundancy=redundancy)

        # 比特转字节
        extracted_bytes = bytearray()
        for i in range(0, len(extracted_bits), 8):
            byte_val = 0
            for j in range(8):
                if i + j < len(extracted_bits):
                    byte_val = (byte_val << 1) | extracted_bits[i + j]
                else:
                    byte_val <<= 1
            extracted_bytes.append(byte_val)

        # 重复解码纠错
        original_data_bit_count = ciphertext_size * 8
        decoded = decode_payload(bytes(extracted_bytes), original_data_bit_count)

        # RSA解密
        try:
            plaintext = rsa_decrypt(rsa_private_key, decoded[:ciphertext_size])
        except Exception as e:
            return {"valid": False, "error": f"RSA解密失败（密钥不匹配或图片未嵌入水印）: {str(e)}"}

        # 解析payload
        result = parse_payload(plaintext)

        # SM2验签（验证水印签名是否与原始图片哈希匹配）
        sig_valid = sm2_verify(
            sm2_public_key,
            result["sm2_signature"],
            bytes.fromhex(result["image_hash"]),
        )

        return {
            "valid": sig_valid,
            "signature_valid": sig_valid,
            "watermark_text": result["watermark_text"],
            "user_id": result["user_id"],
            "timestamp": result["timestamp"],
            "original_hash": result["image_hash"],
            "current_hash": current_hash,
        }

    except Exception as e:
        return {"valid": False, "error": f"验证失败: {str(e)}"}
