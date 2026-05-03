"""DCT域隐形水印嵌入/提取模块

在YCrCb色彩空间的Y通道上，对8x8块进行DCT变换，
在中频系数位置嵌入水印比特。使用JPEG量化表缩放步长以增强鲁棒性。
"""
import numpy as np

# 标准JPEG亮度量化表
JPEG_QUANT_TABLE = np.array([
    [16, 11, 10, 16, 24, 40, 51, 61],
    [12, 12, 14, 19, 26, 58, 60, 55],
    [14, 13, 16, 24, 40, 57, 69, 56],
    [14, 17, 22, 29, 51, 87, 80, 62],
    [18, 22, 37, 56, 68, 109, 103, 77],
    [24, 35, 55, 64, 81, 104, 113, 92],
    [49, 64, 78, 87, 103, 121, 120, 101],
    [72, 92, 95, 98, 112, 100, 103, 99],
], dtype=np.float64)

# 中频系数位置（每个8x8块嵌入4比特）
MID_FREQ_POSITIONS = [(4, 1), (3, 2), (2, 3), (1, 4)]

BITS_PER_BLOCK = len(MID_FREQ_POSITIONS)  # 4


def _dct2_block(block: np.ndarray) -> np.ndarray:
    """2D DCT-II变换（使用numpy实现，无需scipy）"""
    N = block.shape[0]
    result = np.zeros_like(block, dtype=np.float64)
    for u in range(N):
        for v in range(N):
            cu = 1.0 / np.sqrt(2) if u == 0 else 1.0
            cv = 1.0 / np.sqrt(2) if v == 0 else 1.0
            s = 0.0
            for x in range(N):
                for y in range(N):
                    s += block[x, y] * np.cos((2 * x + 1) * u * np.pi / (2 * N)) * np.cos((2 * y + 1) * v * np.pi / (2 * N))
            result[u, v] = 0.25 * cu * cv * s
    return result


def _idct2_block(block: np.ndarray) -> np.ndarray:
    """2D IDCT变换"""
    N = block.shape[0]
    result = np.zeros_like(block, dtype=np.float64)
    for x in range(N):
        for y in range(N):
            s = 0.0
            for u in range(N):
                for v in range(N):
                    cu = 1.0 / np.sqrt(2) if u == 0 else 1.0
                    cv = 1.0 / np.sqrt(2) if v == 0 else 1.0
                    s += cu * cv * block[u, v] * np.cos((2 * x + 1) * u * np.pi / (2 * N)) * np.cos((2 * y + 1) * v * np.pi / (2 * N))
            result[x, y] = 0.25 * s
    return result


def _dct2_fast(block: np.ndarray) -> np.ndarray:
    """使用scipy的快速DCT（如果可用）"""
    try:
        from scipy.fft import dctn
        return dctn(block, type=2, norm='ortho')
    except ImportError:
        return _dct2_block(block)


def _idct2_fast(block: np.ndarray) -> np.ndarray:
    """使用scipy的快速IDCT（如果可用）"""
    try:
        from scipy.fft import idctn
        return idctn(block, type=2, norm='ortho')
    except ImportError:
        return _idct2_block(block)


def embed_watermark(y_channel: np.ndarray, bit_stream: list, alpha: float = 0.35) -> np.ndarray:
    """在Y通道的DCT系数中嵌入水印比特

    Args:
        y_channel: Y通道灰度图 (H, W)，uint8
        bit_stream: 待嵌入的比特列表 [0,1,0,1,...]
        alpha: 嵌入强度，越大越鲁棒但可见性越高

    Returns:
        修改后的Y通道 (H, W)，uint8
    """
    h, w = y_channel.shape
    y = y_channel.astype(np.float64)
    bit_idx = 0

    for row in range(0, h - 7, 8):
        for col in range(0, w - 7, 8):
            if bit_idx >= len(bit_stream):
                break

            block = y[row:row + 8, col:col + 8]
            block_dct = _dct2_fast(block)

            for fr, fc in MID_FREQ_POSITIONS:
                if bit_idx >= len(bit_stream):
                    break

                coeff = block_dct[fr, fc]
                step = max(alpha * abs(JPEG_QUANT_TABLE[fr, fc]), 1.0)
                quantized = round(coeff / step)
                quantized = (quantized & ~1) | bit_stream[bit_idx]
                block_dct[fr, fc] = quantized * step
                bit_idx += 1

            y[row:row + 8, col:col + 8] = np.clip(_idct2_fast(block_dct), 0, 255)

    return y.astype(np.uint8)


def extract_watermark(y_channel: np.ndarray, num_bits: int, alpha: float = 0.35) -> list:
    """从Y通道的DCT系数中提取水印比特

    Args:
        y_channel: Y通道灰度图 (H, W)，uint8
        num_bits: 需要提取的比特数
        alpha: 嵌入强度（必须与嵌入时一致）

    Returns:
        提取的比特列表
    """
    h, w = y_channel.shape
    y = y_channel.astype(np.float64)
    extracted = []

    for row in range(0, h - 7, 8):
        for col in range(0, w - 7, 8):
            if len(extracted) >= num_bits:
                break

            block = y[row:row + 8, col:col + 8]
            block_dct = _dct2_fast(block)

            for fr, fc in MID_FREQ_POSITIONS:
                if len(extracted) >= num_bits:
                    break

                coeff = block_dct[fr, fc]
                step = max(alpha * abs(JPEG_QUANT_TABLE[fr, fc]), 1.0)
                quantized = round(coeff / step)
                extracted.append(quantized & 1)

    return extracted[:num_bits]


def embed_with_redundancy(y_channel: np.ndarray, bit_stream: list, alpha: float = 0.35, redundancy: int = 4) -> np.ndarray:
    """带冗余的水印嵌入（每个比特重复嵌入redundancy次）

    Args:
        y_channel: Y通道
        bit_stream: 比特流
        alpha: 嵌入强度
        redundancy: 冗余次数

    Returns:
        修改后的Y通道
    """
    repeated_bits = []
    for bit in bit_stream:
        repeated_bits.extend([bit] * redundancy)
    return embed_watermark(y_channel, repeated_bits, alpha)


def extract_with_redundancy(y_channel: np.ndarray, num_bits: int, alpha: float = 0.35, redundancy: int = 4) -> list:
    """带冗余的水印提取（多数投票）

    Args:
        y_channel: Y通道
        num_bits: 原始比特数
        alpha: 嵌入强度
        redundancy: 冗余次数

    Returns:
        纠错后的比特列表
    """
    total_bits = num_bits * redundancy
    extracted = extract_watermark(y_channel, total_bits, alpha)

    decoded = []
    for i in range(0, len(extracted), redundancy):
        chunk = extracted[i:i + redundancy]
        ones = sum(chunk)
        decoded.append(1 if ones > redundancy // 2 else 0)

    return decoded[:num_bits]


def get_capacity(image_shape: tuple, redundancy: int = 4) -> int:
    """计算图片的水印容量（比特数）

    Args:
        image_shape: 图片尺寸 (H, W) 或 (H, W, C)
        redundancy: 冗余次数

    Returns:
        可嵌入的原始比特数
    """
    h = image_shape[0]
    w = image_shape[1] if len(image_shape) >= 2 else image_shape[0]
    blocks_h = h // 8
    blocks_w = w // 8
    total_blocks = blocks_h * blocks_w
    total_bits = total_blocks * BITS_PER_BLOCK
    return total_bits // redundancy
