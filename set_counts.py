import argparse
import struct
import sys
import time
import hid

import file_utils

VID = 0x8089
PID = 0x0009
USAGE_PAGE = 0xFF00
REPORT_ID = 2
REPORT_LEN = 64

CMD = 0x50
MAGIC = 0x5A590000
RESP_OFF = 8
KEYS = ("left", "middle", "right")
BACKUP_NAME = "counts_backup.txt"


class ClicksetError(Exception):
    pass


class DeviceNotFound(ClicksetError):
    pass


class DeviceResponseError(ClicksetError):
    pass


class CountValueError(ClicksetError):
    pass


def open_device():
    cands = hid.enumerate(VID, PID)
    if not cands:
        raise DeviceNotFound("No SayoDevice O3C found (VID 0x8089 PID 0x0009). Plugged in?")
    chosen = next((c for c in cands if c.get("usage_page") == USAGE_PAGE), cands[0])
    dev = hid.device()
    try:
        dev.open_path(chosen["path"])
        dev.set_nonblocking(0)
    except Exception:
        dev.close()
        raise
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
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        resp = dev.read(REPORT_LEN, timeout_ms=200)
        if resp:
            return resp
    return []


def packet(mode, vals):
    return struct.pack("<BI4I", mode, MAGIC, *vals)


def read_counts(dev):
    resp = transact(dev, packet(0, (0, 0, 0, 0)))
    if len(resp) < RESP_OFF + 16 or resp[0] != REPORT_ID:
        raise DeviceResponseError("No valid response. Is the click-counter firmware flashed?")
    return list(struct.unpack_from("<4I", bytes(resp), RESP_OFF))


def write_counts(dev, vals):
    resp = transact(dev, packet(1, vals))
    if len(resp) < RESP_OFF + 16 or resp[0] != REPORT_ID:
        raise DeviceResponseError("No valid response to write.")
    return list(struct.unpack_from("<4I", bytes(resp), RESP_OFF))


def merge_counts(current, wanted):
    new = list(current)
    for i, key in enumerate(KEYS):
        value = wanted.get(key)
        if value is None:
            continue
        if not 0 <= value <= 0xFFFFFFFF:
            raise CountValueError("Counts must be 0 .. 4294967295")
        new[i] = value
    return new


def save_backup(path, current):
    contents = f"left={current[0]} middle={current[1]} right={current[2]} slot4={current[3]}\n"
    try:
        file_utils.atomic_write_text(path, contents)
    except OSError as e:
        raise ClicksetError(f"Could not save count backup: {e}") from e


def update_counts(dev, wanted, backup=BACKUP_NAME):
    current = read_counts(dev)
    new = merge_counts(current, wanted)
    save_backup(backup, current)
    previous = write_counts(dev, new)
    after = read_counts(dev)
    return current, new, previous, after


def show(label, vals):
    print(f"{label}: left={vals[0]} middle={vals[1]} right={vals[2]} (slot4={vals[3]})")


def main():
    ap = argparse.ArgumentParser(description="Read/set SayoDevice O3C all-time key press counts")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("read", help="read current all-time counts")
    s = sub.add_parser("set", help="set all-time counts")
    for k in KEYS:
        s.add_argument("--" + k, type=int, help=f"new {k}-key count")
    s.add_argument("--backup", default=BACKUP_NAME, help="file to save current counts to")
    args = ap.parse_args()

    try:
        dev = open_device()
        try:
            if args.cmd == "read":
                show("current", read_counts(dev))
                return

            wanted = {key: getattr(args, key) for key in KEYS}
            current, new, previous, after = update_counts(dev, wanted, args.backup)
        finally:
            dev.close()
    except ClicksetError as e:
        sys.exit(str(e))

    show("current", current)
    print(f"Backup saved to {args.backup}")
    show("writing", new)
    if previous[:3] != current[:3]:
        print("Note: pre-write snapshot differs from first read")
    show("readback", after)
    print("OK" if after[:3] == new[:3]
          else "WARNING: readback does not match")


if __name__ == "__main__":
    main()
