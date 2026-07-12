import argparse
import hashlib
import os

import build_patch
import file_utils
import o3c_fw

EXPECTED_BYTES = {
    build_patch.HOOK: build_patch.DISPLACED,
    build_patch.STUB: bytes(96),
    build_patch.RESTORE: bytes(4),
    build_patch.REJOIN: bytes(4),
}


def apply_patches(dec):
    out = bytearray(dec)
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        if not 0 <= off or off + len(data) > o3c_fw.image_size(dec):
            raise SystemExit(f"Patch at 0x{va:X} is outside the firmware image")
        if dec[off:off + len(data)] != EXPECTED_BYTES[va]:
            raise SystemExit(f"Firmware bytes at patch location 0x{va:X} are unexpected")
        out[off:off + len(data)] = data
    return bytes(out)


def load_decrypted(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise SystemExit(f"Could not read firmware image: {e}") from e

    digest = hashlib.sha256(raw).hexdigest()
    if digest == o3c_fw.STOCK_DECRYPTED_SHA256:
        dec = raw
    elif digest == o3c_fw.STOCK_ENCRYPTED_SHA256:
        dec = o3c_fw.decrypt(raw)
    else:
        raise SystemExit(f"Input is not supported O3C firmware {o3c_fw.VERSION}")
    if not o3c_fw.verify(dec):
        raise SystemExit("Input firmware failed internal verification")
    return dec


def selfcheck(patched_enc, stock_dec):
    dec = o3c_fw.decrypt(patched_enc)
    if not o3c_fw.verify(dec):
        raise SystemExit("Patched image failed internal verification")
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        if dec[off:off + len(data)] != data:
            raise SystemExit(f"Patch is missing at 0x{va:X}")
    untouched = bytearray(dec)
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        untouched[off:off + len(data)] = stock_dec[off:off + len(data)]
    su = bytearray(stock_dec)
    su[o3c_fw.MD5_OFF:o3c_fw.MD5_OFF + 16] = untouched[o3c_fw.MD5_OFF:o3c_fw.MD5_OFF + 16]
    if bytes(untouched) != bytes(su):
        raise SystemExit("Patch changed bytes outside the intended regions")


def build_patched(stock_path, out=None, backup=None):
    stock_dec = load_decrypted(stock_path)
    patched_dec = o3c_fw.fix_md5(apply_patches(stock_dec))
    patched_enc = o3c_fw.encrypt(patched_dec)
    selfcheck(patched_enc, stock_dec)

    out = out or os.path.splitext(stock_path)[0] + "_clickset.bin"
    backup = backup or os.path.splitext(stock_path)[0] + "_stock_backup.bin"
    stock_enc = o3c_fw.encrypt(stock_dec)
    if os.path.exists(backup):
        with open(backup, "rb") as f:
            existing_backup = f.read()
        if existing_backup != stock_enc:
            raise SystemExit(f"Existing stock backup does not match firmware {o3c_fw.VERSION}: {backup}")
    try:
        if not os.path.exists(backup):
            file_utils.atomic_write_bytes(backup, stock_enc)
        file_utils.atomic_write_bytes(out, patched_enc)
    except OSError as e:
        raise SystemExit(f"Could not save patched firmware: {e}") from e
    return out, backup, len(patched_enc), o3c_fw.verify(patched_dec)


def main():
    ap = argparse.ArgumentParser(description="Add the click-counter command to an O3C firmware image")
    ap.add_argument("stock", help="stock firmware")
    ap.add_argument("-o", "--out", help="output patched encrypted image", default=None)
    args = ap.parse_args()

    out, backup, nbytes, md5_ok = build_patched(args.stock, args.out)

    print("Patched image :", out, nbytes, "bytes")
    print("Stock backup  :", backup)
    print("MD5 Verifies  :", md5_ok)
    print("Magic         : 0x%08X" % build_patch.MAGIC)
    print("stub @ VA 0x%X (file 0x%X), hook @ VA 0x8508" % (build_patch.STUB, build_patch.STUB - o3c_fw.LOAD_ADDR))


if __name__ == "__main__":
    main()
