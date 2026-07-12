import argparse
import hashlib
import urllib.request

import file_utils
import o3c_fw

URL = "https://a.sayobot.cn/firmware/update/9/firmware/app_O3C.bin"


def download(out="app_O3C.bin"):
    with urllib.request.urlopen(URL, timeout=60) as r:
        data = r.read()
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != o3c_fw.STOCK_ENCRYPTED_SHA256:
        raise SystemExit(f"Downloaded firmware is not supported O3C firmware {o3c_fw.VERSION}")
    if not o3c_fw.verify(o3c_fw.decrypt(data)):
        raise SystemExit("Downloaded firmware failed internal verification")
    try:
        file_utils.atomic_write_bytes(out, data)
    except OSError as e:
        raise SystemExit(f"Could not save firmware image: {e}") from e
    return len(data), True


def main():
    ap = argparse.ArgumentParser(description="Download the official SayoDevice O3C firmware")
    ap.add_argument("-o", "--out", default="app_O3C.bin")
    args = ap.parse_args()

    n, ok = download(args.out)
    print(f"Downloaded {n} bytes -> {args.out}")
    print(f"Verification: {ok}")
    if not ok:
        print("WARNING: Image failed verification")


if __name__ == "__main__":
    main()
