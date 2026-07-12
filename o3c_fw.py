import hashlib
import struct
from Crypto.Cipher import AES

KEY = bytes.fromhex("C4053DDF225E89F74868C1E1F4C00D514F02A8A8692F997869ABEB155250150C")
IV = bytes(16)

LOAD_ADDR = 0x4000
SIZE_OFF = 0x29F84
MD5_OFF = 0x29FA0
VERSION = "1.4.12"
STOCK_ENCRYPTED_SHA256 = "d81a3e001a2b5f13fcaabfe6a8e357ecaedc14a36ae21cce4f9dc6aed863068f"
STOCK_DECRYPTED_SHA256 = "283611106fc9504f8ffc03a8604c9ec81daade1f2d67960684076b6766b6fd21"


def decrypt(enc):
    return AES.new(KEY, AES.MODE_CBC, IV).decrypt(enc)


def encrypt(dec):
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(dec)


def image_size(dec):
    return struct.unpack_from("<I", dec, SIZE_OFF)[0]


def verify(dec):
    if len(dec) < MD5_OFF + 16:
        return False
    size = image_size(dec)
    if size > len(dec):
        return False
    return dec[MD5_OFF:MD5_OFF + 16] == hashlib.md5(dec[:size]).digest()


def fix_md5(dec):
    out = bytearray(dec)
    out[MD5_OFF:MD5_OFF + 16] = hashlib.md5(bytes(out[:image_size(out)])).digest()
    return bytes(out)
