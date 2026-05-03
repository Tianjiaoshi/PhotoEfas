"""图片文件清理工具

- cleanup_orphan_files(): 清理uploads/outputs中无数据库记录的孤立文件
- cleanup_all_files(): 清理uploads和outputs目录下所有文件
- cleanup_old_files(max_age_hours): 清理超过指定小时数的文件
"""
import os
import time
from pathlib import Path


def cleanup_orphan_files(upload_dir: str, output_dir: str, db_session, WatermarkRecord) -> dict:
    """清理数据库中没有对应记录的孤立文件

    Returns:
        {deleted_uploads: int, deleted_outputs: int, errors: int}
    """
    stats = {"deleted_uploads": 0, "deleted_outputs": 0, "errors": 0}

    # 获取数据库中所有文件路径
    records = WatermarkRecord.query.all()
    known_paths = set()
    for r in records:
        if r.original_image_path:
            known_paths.add(os.path.normpath(r.original_image_path))
        if r.watermarked_image_path:
            known_paths.add(os.path.normpath(r.watermarked_image_path))

    for folder in [upload_dir, output_dir]:
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            fpath = os.path.normpath(os.path.join(folder, f))
            if not os.path.isfile(fpath):
                continue
            if fpath not in known_paths:
                try:
                    os.remove(fpath)
                    if folder == upload_dir:
                        stats["deleted_uploads"] += 1
                    else:
                        stats["deleted_outputs"] += 1
                except OSError:
                    stats["errors"] += 1

    return stats


def cleanup_old_files(upload_dir: str, output_dir: str, max_age_hours: int = 24) -> dict:
    """清理超过指定时间的文件

    Args:
        upload_dir: 上传目录
        output_dir: 输出目录
        max_age_hours: 最大保留小时数

    Returns:
        {deleted: int, errors: int}
    """
    stats = {"deleted": 0, "errors": 0}
    cutoff = time.time() - max_age_hours * 3600

    for folder in [upload_dir, output_dir]:
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            fpath = os.path.join(folder, f)
            if not os.path.isfile(fpath):
                continue
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    stats["deleted"] += 1
            except OSError:
                stats["errors"] += 1

    return stats


def cleanup_all_files(upload_dir: str, output_dir: str) -> dict:
    """清空uploads和outputs目录

    Returns:
        {deleted: int, errors: int}
    """
    stats = {"deleted": 0, "errors": 0}

    for folder in [upload_dir, output_dir]:
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            fpath = os.path.join(folder, f)
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                    stats["deleted"] += 1
                except OSError:
                    stats["errors"] += 1

    return stats


def get_folder_size(folder: str) -> int:
    """获取目录下所有文件的总大小（字节）"""
    total = 0
    if not os.path.isdir(folder):
        return 0
    for f in os.listdir(folder):
        fpath = os.path.join(folder, f)
        if os.path.isfile(fpath):
            total += os.path.getsize(fpath)
    return total


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
