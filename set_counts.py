import argparse
import struct
import sys
import time
import hid

VID = 0x8089
PID = 0x0009
USAGE_PAGE = 0xFF00
REPORT_ID = 2
REPORT_LEN = 64

CMD = 0x50
MAGIC = 0x5A590000
RESP_OFF = 8
KEYS = ("left", "middle", "right")


def open_device():
    cands = hid.enumerate(VID, PID)
    if not cands:
        sys.exit("No SayoDevice O3C found (VID 0x8089 PID 0x0009). Plugged in?")
    chosen = next((c for c in cands if c.get("usage_page") == USAGE_PAGE), cands[0])
    dev = hid.device()
    dev.open_path(chosen["path"])
    dev.set_nonblocking(0)
    return dev


def build(payload):
    buf = bytearray(REPORT_LEN)
    buf[0] = REPORT_ID
    buf[1] = CMD
    buf[2] = len(payload)
    buf[3:3 + len(payload)] = payload
    buf[3 + len(payload)] = (REPORT_ID + CMD + len(payload) + sum(payload)) & 0xFF
    return list(buf)


def transact(dev, payload, timeout_ms=1000):
    dev.write(build(payload))
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        resp = dev.read(REPORT_LEN, timeout_ms=200)
        if resp:
            return resp
    return []


def packet(mode, vals):
    return struct.pack("<BI4I", mode, MAGIC, *vals)


def read_counts(dev):
    resp = transact(dev, packet(0, (0, 0, 0, 0)))
    if not resp or resp[0] != REPORT_ID:
        sys.exit("No valid response. Is the click-counter firmware flashed?")
    return list(struct.unpack_from("<4I", bytes(resp), RESP_OFF))


def write_counts(dev, vals):
    resp = transact(dev, packet(1, vals))
    if not resp or resp[0] != REPORT_ID:
        sys.exit("No valid response to write.")
    return list(struct.unpack_from("<4I", bytes(resp), RESP_OFF))


def show(label, vals):
    print(f"{label}: left={vals[0]} middle={vals[1]} right={vals[2]} (slot4={vals[3]})")


def main():
    ap = argparse.ArgumentParser(description="Read/set SayoDevice O3C all-time key press counts")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("read", help="read current all-time counts")
    s = sub.add_parser("set", help="set all-time counts")
    for k in KEYS:
        s.add_argument("--" + k, type=int, help=f"new {k}-key count")
    s.add_argument("--backup", default="counts_backup.txt", help="file to save current counts to")
    args = ap.parse_args()

    dev = open_device()
    current = read_counts(dev)
    show("current", current)

    if args.cmd == "read":
        return

    for v in (getattr(args, k) for k in KEYS):
        if v is not None and not (0 <= v <= 0xFFFFFFFF):
            sys.exit("Counts must be 0 .. 4294967295")

    with open(args.backup, "w") as f:
        f.write(f"left={current[0]} middle={current[1]} right={current[2]} slot4={current[3]}\n")
    print(f"Backup saved to {args.backup}")

    new = list(current)
    for i, k in enumerate(KEYS):
        v = getattr(args, k)
        if v is not None:
            new[i] = v
    show("writing", new)
    prev = write_counts(dev, new)
    if prev[:3] != current[:3]:
        print("Note: pre-write snapshot differs from first read")
    after = read_counts(dev)
    show("readback", after)
    print("OK" if after[:3] == new[:3]
          else "WARNING: readback does not match")


if __name__ == "__main__":
    main()
