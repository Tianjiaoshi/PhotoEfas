"""SM2(国密) + RSA 混合加密模块

SM2: 用于数字签名（完整性 + 不可否认性）
RSA-2048 OAEP: 用于加密水印payload（机密性）
SM3: 用于哈希计算
"""
import hashlib
import struct
import os
from datetime import datetime

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from gmssl import sm2, func


# ============ SM2 椭圆曲线参数 ============

_ECC_TABLE = sm2.default_ecc_table
_N = int(_ECC_TABLE['n'], 16)
_P = int(_ECC_TABLE['p'], 16)
_A = int(_ECC_TABLE['a'], 16)
_G_STR = _ECC_TABLE['g']
_Gx = int(_G_STR[:64], 16)
_Gy = int(_G_STR[64:], 16)


def _point_add(x1, y1, x2, y2):
    """椭圆曲线点加法"""
    if x1 == 0 and y1 == 0:
        return x2, y2
    if x2 == 0 and y2 == 0:
        return x1, y1
    if x1 == x2 and y1 == y2:
        return _point_double(x1, y1)
    if x1 == x2:
        return 0, 0
    lam = ((y2 - y1) * pow(x2 - x1, -1, _P)) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return x3, y3


def _point_double(x, y):
    """椭圆曲线点倍乘"""
    lam = ((3 * x * x + _A) * pow(2 * y, -1, _P)) % _P
    x3 = (lam * lam - 2 * x) % _P
    y3 = (lam * (x - x3) - y) % _P
    return x3, y3


def _point_mul(k, Px, Py):
    """标量乘法 Q = k * P（double-and-add）"""
    Rx, Ry = 0, 0
    Qx, Qy = Px, Py
    while k > 0:
        if k & 1:
            Rx, Ry = _point_add(Rx, Ry, Qx, Qy)
        Qx, Qy = _point_double(Qx, Qy)
        k >>= 1
    return Rx, Ry


# ============ SM2 操作 ============

def generate_sm2_keypair() -> tuple:
    """生成SM2密钥对

    Returns:
        (private_key_hex, public_key_hex)
        private_key_hex: 64字符hex
        public_key_hex: 128字符hex (不含04前缀)
    """
    while True:
        d = int.from_bytes(os.urandom(32), 'big')
        if 1 < d < _N - 1:
            break

    private_key_hex = format(d, '064x')
    Qx, Qy = _point_mul(d, _Gx, _Gy)
    public_key_hex = format(Qx, '064x') + format(Qy, '064x')
    return private_key_hex, public_key_hex


def sm2_sign(private_key_hex: str, data: bytes) -> str:
    """SM2签名（使用SM3哈希）

    Args:
        private_key_hex: SM2私钥（64字符hex）
        data: 待签名数据

    Returns:
        签名（hex字符串）
    """
    # 需要一个公钥来构造CryptSM2实例，但签名只需要私钥
    # 计算对应的公钥
    d = int(private_key_hex, 16)
    Qx, Qy = _point_mul(d, _Gx, _Gy)
    pub_hex = format(Qx, '064x') + format(Qy, '064x')

    sm2_crypt = sm2.CryptSM2(private_key=private_key_hex, public_key=pub_hex)
    random_hex = func.random_hex(sm2_crypt.para_len)
    return sm2_crypt.sign(data, random_hex)


def sm2_verify(public_key_hex: str, signature_hex: str, data: bytes) -> bool:
    """SM2验签

    Args:
        public_key_hex: SM2公钥（128字符hex，不含04前缀）
        signature_hex: 签名（hex字符串）
        data: 原始数据

    Returns:
        签名是否有效
    """
    try:
        sm2_crypt = sm2.CryptSM2(private_key="", public_key=public_key_hex)
        return sm2_crypt.verify(signature_hex, data)
    except Exception:
        return False


def sm2_sign_with_sm3(private_key_hex: str, data: bytes) -> str:
    """SM2签名（内部使用SM3，推荐）"""
    d = int(private_key_hex, 16)
    Qx, Qy = _point_mul(d, _Gx, _Gy)
    pub_hex = format(Qx, '064x') + format(Qy, '064x')

    sm2_crypt = sm2.CryptSM2(private_key=private_key_hex, public_key=pub_hex)
    random_hex = func.random_hex(sm2_crypt.para_len)
    return sm2_crypt.sign_with_sm3(data, random_hex)


def sm2_verify_with_sm3(public_key_hex: str, signature_hex: str, data: bytes) -> bool:
    """SM2验签（内部使用SM3）"""
    try:
        sm2_crypt = sm2.CryptSM2(private_key="", public_key=public_key_hex)
        return sm2_crypt.verify_with_sm3(signature_hex, data)
    except Exception:
        return False


# ============ SM3 哈希 ============

def sm3_hash(data: bytes) -> str:
    """计算SM3哈希"""
    from gmssl.sm3 import sm3_hash as _sm3
    return _sm3(list(data))


# ============ RSA 操作 ============

def generate_rsa_keypair(bits: int = 2048) -> tuple:
    """生成RSA密钥对

    Returns:
        (private_pem, public_pem) PEM格式字符串
    """
    key = RSA.generate(bits)
    private_pem = key.export_key().decode("utf-8")
    public_pem = key.publickey().export_key().decode("utf-8")
    return private_pem, public_pem


def rsa_encrypt(public_key_pem: str, data: bytes) -> bytes:
    """RSA-OAEP加密（最大约190字节 for 2048-bit key）"""
    key = RSA.import_key(public_key_pem)
    cipher = PKCS1_OAEP.new(key)
    return cipher.encrypt(data)


def rsa_decrypt(private_key_pem: str, ciphertext: bytes) -> bytes:
    """RSA-OAEP解密"""
    key = RSA.import_key(private_key_pem)
    cipher = PKCS1_OAEP.new(key)
    return cipher.decrypt(ciphertext)


# ============ Payload 构建/解析 ============

def build_payload(watermark_text: str, user_id: int, image_hash: str, sm2_sig: str) -> bytes:
    """构建水印payload二进制格式

    格式: [2B text_len][text][4B user_id][26B timestamp][32B hash][2B sig_len][sig]
    """
    text_bytes = watermark_text.encode("utf-8")[:64]
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S").encode("utf-8")[:26]
    hash_bytes = bytes.fromhex(image_hash)[:32]
    sig_bytes = bytes.fromhex(sm2_sig) if len(sm2_sig) % 2 == 0 else sm2_sig.encode("utf-8")

    payload = struct.pack("!H", len(text_bytes))
    payload += text_bytes
    payload += struct.pack("!I", user_id)
    payload += timestamp.ljust(26, b'\x00')
    payload += hash_bytes.ljust(32, b'\x00')
    payload += struct.pack("!H", len(sig_bytes))
    payload += sig_bytes
    return payload


def parse_payload(data: bytes) -> dict:
    """解析水印payload"""
    offset = 0

    text_len = struct.unpack("!H", data[offset:offset + 2])[0]
    offset += 2
    watermark_text = data[offset:offset + text_len].decode("utf-8", errors="replace")
    offset += text_len

    user_id = struct.unpack("!I", data[offset:offset + 4])[0]
    offset += 4

    timestamp = data[offset:offset + 26].rstrip(b'\x00').decode("utf-8", errors="replace")
    offset += 26

    image_hash = data[offset:offset + 32].hex()
    offset += 32

    sig_len = struct.unpack("!H", data[offset:offset + 2])[0]
    offset += 2
    sm2_sig = data[offset:offset + sig_len].hex()

    return {
        "watermark_text": watermark_text,
        "user_id": user_id,
        "timestamp": timestamp,
        "image_hash": image_hash,
        "sm2_signature": sm2_sig,
    }


def get_payload_size(watermark_text_len: int = 64) -> int:
    """估算payload大小"""
    return 2 + watermark_text_len + 4 + 26 + 32 + 2 + 64  # ~194字节
