import argparse
import os
import o3c_fw
import build_patch


def apply_patches(dec):
    out = bytearray(dec)
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        assert 0 <= off and off + len(data) <= o3c_fw.image_size(dec), f"Patch at 0x{va:X} outside image"
        out[off:off + len(data)] = data
    return bytes(out)


def load_decrypted(path):
    raw = open(path, "rb").read()
    if o3c_fw.verify(raw):
        return raw
    dec = o3c_fw.decrypt(raw)
    if o3c_fw.verify(dec):
        return dec
    raise SystemExit("Input is neither a valid decrypted image nor a decryptable stock image")


def selfcheck(patched_enc, stock_dec):
    dec = o3c_fw.decrypt(patched_enc)
    assert o3c_fw.verify(dec), "Patched image MD5 does not verify"
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        assert dec[off:off + len(data)] == data, f"Patch missing at 0x{va:X}"
    untouched = bytearray(dec)
    for va, data in build_patch.patches():
        off = va - o3c_fw.LOAD_ADDR
        untouched[off:off + len(data)] = stock_dec[off:off + len(data)]
    su = bytearray(stock_dec)
    su[o3c_fw.MD5_OFF:o3c_fw.MD5_OFF + 16] = untouched[o3c_fw.MD5_OFF:o3c_fw.MD5_OFF + 16]
    assert bytes(untouched) == bytes(su), "Patch changed bytes outside the intended regions"


def build_patched(stock_path, out=None, backup=None):
    stock_dec = load_decrypted(stock_path)
    patched_dec = o3c_fw.fix_md5(apply_patches(stock_dec))
    patched_enc = o3c_fw.encrypt(patched_dec)
    selfcheck(patched_enc, stock_dec)

    out = out or os.path.splitext(stock_path)[0] + "_clickset.bin"
    backup = backup or os.path.splitext(stock_path)[0] + "_stock_backup.bin"
    open(out, "wb").write(patched_enc)
    if not os.path.exists(backup):
        open(backup, "wb").write(o3c_fw.encrypt(stock_dec))
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
