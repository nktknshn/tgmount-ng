from tgmount.util import none_fallback, random_int, nn


def random_file_reference() -> bytes:
    return bytes([random_int(255)() for _ in range(0, 32)])
