import argparse
import urllib.request
import o3c_fw

URL = "https://a.sayobot.cn/firmware/update/9/firmware/app_O3C.bin"


def download(out="app_O3C.bin"):
    with urllib.request.urlopen(URL, timeout=60) as r:
        data = r.read()
    open(out, "wb").write(data)
    return len(data), o3c_fw.verify(o3c_fw.decrypt(data))


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
