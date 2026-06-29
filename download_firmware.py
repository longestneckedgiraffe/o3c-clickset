import argparse
import urllib.request
import o3c_fw

URL = "https://a.sayobot.cn/firmware/update/9/firmware/app_O3C.bin"


def main():
    ap = argparse.ArgumentParser(description="Download the official SayoDevice O3C firmware")
    ap.add_argument("-o", "--out", default="app_O3C.bin")
    args = ap.parse_args()

    with urllib.request.urlopen(URL, timeout=60) as r:
        data = r.read()
    open(args.out, "wb").write(data)

    dec = o3c_fw.decrypt(data)
    ok = o3c_fw.verify(dec)
    print(f"Downloaded {len(data)} bytes -> {args.out}")
    print(f"Verification: {ok}")
    if not ok:
        print("WARNING: Image failed verification")


if __name__ == "__main__":
    main()
