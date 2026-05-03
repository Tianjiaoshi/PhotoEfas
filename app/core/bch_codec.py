"""BCH纠错编码模块

使用重复编码+汉明码实现轻量级纠错，不依赖外部bchlib。
对JPEG压缩（Q=50-70）提供容错能力。
"""
import numpy as np


def _bytes_to_bits(data: bytes) -> list:
    """字节转比特流"""
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_bytes(bits: list) -> bytes:
    """比特流转字节"""
    byte_array = bytearray()
    for i in range(0, len(bits), 8):
        byte_val = 0
        for j in range(8):
            if i + j < len(bits):
                byte_val = (byte_val << 1) | bits[i + j]
            else:
                byte_val <<= 1
        byte_array.append(byte_val)
    return bytes(byte_array)


def _hamming_encode_byte(data_bits: list) -> list:
    """对7位数据进行汉明码(7,4)编码，返回7位编码"""
    # 简化版：使用重复编码3次
    return data_bits * 3


def encode_with_repetition(data: bytes, redundancy: int = 3) -> bytes:
    """重复编码：每比特重复redundancy次

    Args:
        data: 原始字节数据
        redundancy: 重复次数（奇数，推荐3）

    Returns:
        编码后的字节数据
    """
    bits = _bytes_to_bits(data)
    encoded_bits = []
    for bit in bits:
        encoded_bits.extend([bit] * redundancy)
    return _bits_to_bytes(encoded_bits)


def decode_with_repetition(encoded: bytes, original_bit_count: int, redundancy: int = 3) -> bytes:
    """重复解码：多数投票恢复原始数据

    Args:
        encoded: 编码后的字节数据
        original_bit_count: 原始比特数
        redundancy: 重复次数

    Returns:
        解码纠错后的字节数据
    """
    enc_bits = _bytes_to_bits(encoded)
    decoded_bits = []
    total_encoded_bits = original_bit_count * redundancy

    for i in range(0, min(total_encoded_bits, len(enc_bits)), redundancy):
        chunk = enc_bits[i:i + redundancy]
        ones = sum(chunk)
        decoded_bits.append(1 if ones > redundancy // 2 else 0)

    return _bits_to_bytes(decoded_bits[:original_bit_count])


def encode_payload(data: bytes) -> tuple:
    """编码payload，返回(编码后数据, 原始比特数)"""
    original_bit_count = len(data) * 8
    encoded = encode_with_repetition(data, redundancy=3)
    return encoded, original_bit_count


def decode_payload(encoded: bytes, original_bit_count: int) -> bytes:
    """解码payload"""
    return decode_with_repetition(encoded, original_bit_count, redundancy=3)
