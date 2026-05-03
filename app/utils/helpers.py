import os
import uuid
from pathlib import Path
from flask import current_app

# 允许的扩展名
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp"}

# 文件头 Magic Bytes 签名
MAGIC_BYTES = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"BM": "bmp",
}


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许（仅用于初步筛选）"""
    if "." not in filename:
        return False
    # 取最后一个扩展名，防止 double extension 攻击 (shell.php.png)
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _verify_file_content(file_stream) -> str | None:
    """通过 Magic Bytes 验证文件实际类型

    Returns:
        验证通过的扩展名，或 None（非图片文件）
    """
    header = file_stream.read(16)
    file_stream.seek(0)  # 重置读取位置

    for magic, ext in MAGIC_BYTES.items():
        if header.startswith(magic):
            return ext
    return None


def save_upload(file, upload_folder: str) -> str | None:
    """保存上传文件，返回保存路径

    安全措施：
    1. 验证扩展名白名单
    2. 通过 Magic Bytes 验证文件实际内容是图片
    3. 使用 UUID 文件名防止路径遍历和文件名注入
    """
    if not file or not file.filename:
        return None

    # 1. 扩展名白名单检查
    orig_name = file.filename
    if "." not in orig_name:
        return None

    ext = orig_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None

    # 2. Magic Bytes 内容验证 - 防止上传伪装的 PHP/JSP/ASPX 等恶意文件
    verified_ext = _verify_file_content(file.stream)
    if verified_ext is None:
        return None
    # 使用实际验证通过的扩展名（防止扩展名与内容不一致）
    ext = verified_ext

    # 3. UUID 文件名 - 防止路径遍历、文件名注入、双写绕过
    unique_name = f"{uuid.uuid4().hex[:12]}.{ext}"

    Path(upload_folder).mkdir(parents=True, exist_ok=True)
    filepath = str(Path(upload_folder) / unique_name)

    try:
        file.save(filepath)
        return filepath
    except Exception:
        return None
