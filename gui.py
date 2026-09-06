import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import download_firmware
import flash_firmware
import patch_firmware
import set_counts

PAD = 10
STOCK_NAME = "app_O3C.bin"
MUTED = "#666"
ERROR = "#b00020"
OK = "#137333"
CTRL_CLOSE_EXIT = 0xC000013A

root = None
status = progress = output = None

state = {}
count_current = {}
count_entry = {}
read_btn = write_btn = None
action_buttons = []
ui_events = queue.Queue()
busy = False


def log(text, tag=None):
    output["state"] = "normal"
    output.insert("end", text + "\n", (tag,) if tag else ())
    output.see("end")
    output["state"] = "disabled"


def post_ui(fn):
    ui_events.put(fn)


def process_ui_events():
    try:
        while True:
            ui_events.get_nowait()()
    except queue.Empty:
        pass
    finally:
        root.after(25, process_ui_events)


def set_busy(value):
    global busy
    busy = value
    button_state = "disabled" if value else "normal"
    for button in action_buttons:
        button["state"] = button_state


def run_async(busy_message, work, on_done):
    if busy:
        return
    set_busy(True)
    status.set(busy_message)
    progress.config(mode="indeterminate")
    progress.start(18)

    def finish(result, err):
        set_busy(False)
        progress.stop()
        progress.config(mode="determinate", value=0)
        if err is not None:
            status.set(err)
            messagebox.showerror("Error", err)
        else:
            on_done(result)

    def worker():
        try:
            result, err = work(), None
        except SystemExit as e:
            result, err = None, str(e.code)
        except Exception as e:
            result, err = None, str(e)
        post_ui(lambda: finish(result, err))

    threading.Thread(target=worker, daemon=True).start()


def with_device(fn):
    dev = set_counts.open_device()
    try:
        return fn(dev)
    finally:
        dev.close()


def fmt_counts(vals):
    return f"left {vals[0]:,}   middle {vals[1]:,}   right {vals[2]:,}"


def parse_count(s):
    s = s.strip()
    if not s:
        return None, None
    if not s.isdecimal():
        return None, "must be a whole number"
    try:
        v = int(s)
    except ValueError:
        return None, "must be 0 .. 4294967295"
    if v > 0xFFFFFFFF:
        return None, "must be 0 .. 4294967295"
    return v, None


def pick_open(entry):
    path = filedialog.askopenfilename(title="Select firmware image")
    if path:
        set_entry(entry, path)


def set_entry(entry, text):
    entry.delete(0, "end")
    entry.insert(0, text)


def section(parent, title):
    f = ttk.LabelFrame(parent, text=title, padding=PAD)
    f.pack(fill="x", pady=(0, PAD))
    return f


def build_download(parent):
    f = section(parent, "Download")
    btn = ttk.Button(f, text="Download", width=18)
    btn.pack(anchor="w")
    action_buttons.append(btn)

    def done(res):
        n, ok = res
        if not state["patch_stock"].get().strip():
            set_entry(state["patch_stock"], STOCK_NAME)
        log(f"Saved {n:,} bytes to {STOCK_NAME}", "ok")
        log("Verified: yes" if ok else "Verified: NO", "ok" if ok else "warn")
        status.set(f"Downloaded {STOCK_NAME}" if ok else f"Downloaded {STOCK_NAME} (failed verify)")

    btn.configure(command=lambda: run_async(
        "Downloading firmware...", lambda: download_firmware.download(STOCK_NAME), done))


def build_patch(parent):
    f = section(parent, "Patch")
    g = ttk.Frame(f)
    g.pack(fill="x")
    g.columnconfigure(1, weight=1)

    ttk.Label(g, text="Input").grid(row=0, column=0, sticky="w")
    stock = ttk.Entry(g)
    stock.grid(row=0, column=1, sticky="we", padx=(4, 8))
    ttk.Button(g, text="Browse", width=10, command=lambda: pick_open(stock)).grid(row=0, column=2)

    state["patch_stock"] = stock

    btn = ttk.Button(f, text="Build", width=18)
    btn.pack(anchor="w", pady=(8, 0))
    action_buttons.append(btn)

    def go():
        s = stock.get().strip()
        if not s:
            messagebox.showerror("Error", "Choose a firmware image first.")
            return
        run_async("Building patched image...", lambda: patch_firmware.build_patched(s, None), done)

    def done(res):
        o, b, n, ok = res
        set_entry(state["flash_img"], o)
        log(f"Patched image: {o}", "ok")
        log(f"Stock backup:  {b}")
        log(f"Verified: {'yes' if ok else 'NO'}   ({n:,} bytes)", "ok" if ok else "warn")
        status.set(f"Built {o}" if ok else f"Built {o} (failed verify)")

    btn.configure(command=go)


def build_flash(parent):
    f = section(parent, "Flash")
    g = ttk.Frame(f)
    g.pack(fill="x")
    g.columnconfigure(1, weight=1)

    ttk.Label(g, text="Image").grid(row=0, column=0, sticky="w")
    img = ttk.Entry(g)
    img.insert(0, "app_O3C_clickset.bin")
    img.grid(row=0, column=1, sticky="we", padx=(4, 8))
    ttk.Button(g, text="Browse", width=10, command=lambda: pick_open(img)).grid(row=0, column=2)
    state["flash_img"] = img

    btn = ttk.Button(f, text="Flash", width=18)
    btn.pack(anchor="w", pady=(8, 0))
    action_buttons.append(btn)

    def go():
        image_path = img.get().strip()
        if not image_path:
            messagebox.showerror("Error", "Choose a firmware image to flash.")
            return

        def line(s):
            post_ui(lambda: (log(s), status.set(s)))

        run_async("Flashing firmware...", lambda: flash_firmware.flash(
            image_path, on_line=line, gui=True), done)

    def done(code):
        if code == 0 or code == CTRL_CLOSE_EXIT:
            log("Flash complete.", "ok")
            status.set("Flash complete")
        else:
            log(f"Flash finished with code {code} (see output).", "warn")
            status.set(f"Flash failed (code {code})")
        root.after(1000, refresh_device)

    btn.configure(command=go)


def show_current(vals):
    for i, k in enumerate(set_counts.KEYS):
        count_current[k].config(text=f"{vals[i]:,}")
    log("Current: " + fmt_counts(vals), "ok")


def build_counts(parent):
    global read_btn, write_btn
    f = section(parent, "Counts")

    g = ttk.Frame(f)
    g.pack(anchor="w")
    ttk.Label(g, text="Current", foreground=MUTED).grid(row=0, column=1, padx=12)
    ttk.Label(g, text="New", foreground=MUTED).grid(row=0, column=2)
    for i, k in enumerate(set_counts.KEYS):
        ttk.Label(g, text=k.capitalize(), width=8, anchor="w").grid(row=i + 1, column=0, sticky="w", pady=2)
        cur = ttk.Label(g, text="-", width=12, anchor="e")
        cur.grid(row=i + 1, column=1, padx=12)
        e = ttk.Entry(g, width=14)
        e.grid(row=i + 1, column=2)
        count_current[k] = cur
        count_entry[k] = e

    br = ttk.Frame(f)
    br.pack(anchor="w", pady=(PAD, 0))
    read_btn = ttk.Button(br, text="Read", width=12)
    read_btn.grid(row=0, column=0, padx=(0, 6))
    write_btn = ttk.Button(br, text="Write", width=12)
    write_btn.grid(row=0, column=1)
    action_buttons.extend((read_btn, write_btn))

    def did_read(vals):
        show_current(vals)
        status.set("Counts read")

    read_btn.configure(command=lambda: run_async(
        "Reading counts...", lambda: with_device(set_counts.read_counts), did_read))
    write_btn.configure(command=do_write)


def do_write():
    wanted = {}
    for k in set_counts.KEYS:
        v, err = parse_count(count_entry[k].get())
        if err:
            messagebox.showerror("Error", f"{k.capitalize()} {err}.")
            return
        wanted[k] = v

    def after_write(result):
        current, new, previous, after = result
        show_current(current)
        log(f"Backup saved to {set_counts.BACKUP_NAME}")
        if previous[:3] != current[:3]:
            log("Pre-write snapshot differs from first read", "warn")
        show_current(after)
        if after[:3] == new[:3]:
            log("Counts written.", "ok")
            status.set("Counts written")
        else:
            log("Readback mismatch", "warn")
            status.set("Readback mismatch")
            messagebox.showwarning(
                "Readback mismatch",
                "The values read back do not match what was written.\n"
                "Key presses between write and read can cause this.")

    run_async("Writing counts...", lambda: with_device(
        lambda dev: set_counts.update_counts(dev, wanted)), after_write)


def probe_device():
    try:
        dev = set_counts.open_device()
    except set_counts.DeviceNotFound:
        return "absent", None
    try:
        vals = set_counts.read_counts(dev)
    except set_counts.DeviceResponseError:
        return "stock", None
    finally:
        dev.close()
    if vals[:3] == [0, 0, 0]:
        return "stock", vals
    return "clickset", vals


def refresh_device():
    if busy:
        root.after(250, refresh_device)
        return
    run_async("Checking device...", probe_device, apply_device)


def apply_device(res):
    code, vals = res
    if code == "clickset":
        status.set("Device connected (clickset firmware)")
        show_current(vals)
    elif code == "stock":
        status.set("Device connected (stock firmware)")
    else:
        status.set("No device found")


def build_ui(window):
    global root, status, progress, output
    root = window
    root.title("clickset")
    root.minsize(560, 600)
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    bar = ttk.Frame(root, relief="groove", padding=(PAD, 4))
    bar.pack(side="bottom", fill="x")
    status = tk.StringVar(value="Checking device...")
    ttk.Label(bar, textvariable=status, foreground=MUTED).pack(side="left")
    progress = ttk.Progressbar(bar, mode="determinate", length=160)
    progress.pack(side="right")

    out_frame = ttk.LabelFrame(root, text="Output", padding=(PAD, 4))
    out_frame.pack(side="bottom", fill="both", expand=True, padx=PAD, pady=(0, 6))
    scroll = ttk.Scrollbar(out_frame)
    scroll.pack(side="right", fill="y")
    output = tk.Text(out_frame, height=5, wrap="word", state="disabled",
                     relief="flat", background="#f6f6f6", yscrollcommand=scroll.set)
    output.pack(side="left", fill="both", expand=True)
    scroll.config(command=output.yview)
    output.tag_config("warn", foreground=ERROR)
    output.tag_config("ok", foreground=OK)

    content = ttk.Frame(root, padding=(PAD, PAD, PAD, 0))
    content.pack(side="top", fill="x")
    build_download(content)
    build_patch(content)
    build_flash(content)
    build_counts(content)

    root.after(25, process_ui_events)
    root.after(150, refresh_device)


def main():
    root = tk.Tk()
    build_ui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
