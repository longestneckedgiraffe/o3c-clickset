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

root = None
status = progress = output = None

state = {}
count_current = {}
count_entry = {}
read_btn = write_btn = None


def set_status(message):
    status.set(message)


def log(text, tag=None):
    output["state"] = "normal"
    output.insert("end", text + "\n", (tag,) if tag else ())
    output.see("end")
    output["state"] = "disabled"


def run_async(button, busy_message, work, on_done):
    button["state"] = "disabled"
    set_status(busy_message)
    progress.config(mode="indeterminate")
    progress.start(18)

    def finish(result, err):
        button["state"] = "normal"
        progress.stop()
        progress.config(mode="determinate", value=0)
        if err is not None:
            set_status(err)
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
        button.after(0, lambda: finish(result, err))

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
    if not s.isdigit():
        return None, "must be a whole number"
    v = int(s)
    if v > 0xFFFFFFFF:
        return None, "must be 0 .. 4294967295"
    return v, None


def pick_open(entry):
    path = filedialog.askopenfilename(title="Select firmware image")
    if path:
        set_entry(entry, path)


def pick_save(entry, default):
    path = filedialog.asksaveasfilename(title="Save as", initialfile=default, defaultextension=".bin")
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

    def done(res):
        n, ok = res
        if not state["patch_stock"].get().strip():
            set_entry(state["patch_stock"], STOCK_NAME)
        log(f"Saved {n:,} bytes to {STOCK_NAME}", "ok")
        log("Verified: yes" if ok else "Verified: NO", "ok" if ok else "warn")
        set_status(f"Downloaded {STOCK_NAME}" if ok else f"Downloaded {STOCK_NAME} (failed verify)")

    btn.configure(command=lambda: run_async(
        btn, "Downloading firmware...", lambda: download_firmware.download(STOCK_NAME), done))


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

    def work():
        s = stock.get().strip()
        if not s:
            raise SystemExit("Choose a firmware image first.")
        return patch_firmware.build_patched(s, None)

    def done(res):
        o, b, n, ok = res
        set_entry(state["flash_img"], o)
        log(f"Patched image: {o}", "ok")
        log(f"Stock backup:  {b}")
        log(f"Verified: {'yes' if ok else 'NO'}   ({n:,} bytes)", "ok" if ok else "warn")
        set_status(f"Built {o}" if ok else f"Built {o} (failed verify)")

    btn.configure(command=lambda: run_async(btn, "Building patched image...", work, done))


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

    def work():
        if not img.get().strip():
            raise SystemExit("Choose a firmware image to flash.")

        def line(s):
            btn.after(0, lambda: (log(s), set_status(s)))

        return flash_firmware.flash(img.get().strip(), on_line=line, gui=True)

    def done(code):
        if code == 0:
            log("Flash complete.", "ok")
            set_status("Flash complete")
            refresh_device()
        else:
            log(f"Flash finished with code {code} (see output).", "warn")
            set_status(f"Flash failed (code {code})")

    def go():
        if not messagebox.askyesno(
                "clickset",
                "Please confirm that your device is in bootloader mode\nHold your Sayodevice's knob for 2-3 seconds -> Device -> Factory Recovery -> Jump to bootloader\n\n"
                "Do not unplug during flashing!\nContinue?"):
            set_status("Flash cancelled")
            return
        run_async(btn, "Flashing firmware...", work, done)

    btn.configure(command=go)


def show_current(vals):
    state["last_read"] = vals
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

    def did_read(vals):
        show_current(vals)
        set_status("Counts read")

    read_btn.configure(command=lambda: run_async(
        read_btn, "Reading counts...", lambda: with_device(set_counts.read_counts), did_read))
    write_btn.configure(command=do_write)


def do_write():
    wanted = {}
    for k in set_counts.KEYS:
        v, err = parse_count(count_entry[k].get())
        if err:
            messagebox.showerror("Error", f"{k.capitalize()} {err}.")
            return
        wanted[k] = v

    def after_read(current):
        show_current(current)
        if not messagebox.askyesno(
                "Safety check",
                "The current values shown must match the all-time counts on your device "
                "screen.\n\nIf they do not match, choose No to abort.\n\nDo they match?"):
            set_status("Write aborted")
            return
        new = list(current)
        for i, k in enumerate(set_counts.KEYS):
            if wanted[k] is not None:
                new[i] = wanted[k]

        def after_write(res):
            _, after = res
            show_current(after)
            if after[:3] == new[:3]:
                log("Counts written.", "ok")
                set_status("Counts written")
            else:
                log("Readback mismatch", "warn")
                set_status("Readback mismatch")
                messagebox.showwarning(
                    "Readback mismatch",
                    "The values read back do not match what was written.\n"
                    "Key presses between write and read can cause this.")

        run_async(write_btn, "Writing counts...", lambda: with_device(
            lambda dev: (set_counts.write_counts(dev, new), set_counts.read_counts(dev))), after_write)

    run_async(write_btn, "Reading counts...", lambda: with_device(set_counts.read_counts), after_read)


def probe_device():
    try:
        dev = set_counts.open_device()
    except SystemExit:
        return "absent", None
    try:
        vals = set_counts.read_counts(dev)
    except SystemExit:
        return "stock", None
    finally:
        dev.close()
    if vals[:3] == [0, 0, 0]:
        return "stock", vals
    return "clickset", vals


def refresh_device():
    set_status("Checking device...")

    def worker():
        res = probe_device()
        root.after(0, lambda: apply_device(res))

    threading.Thread(target=worker, daemon=True).start()


def apply_device(res):
    code, vals = res
    if code == "clickset":
        set_status("Device connected (clickset firmware)")
        show_current(vals)
    elif code == "stock":
        set_status("Device connected (stock firmware)")
    else:
        set_status("No device found")


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

    root.after(150, refresh_device)


def main():
    root = tk.Tk()
    build_ui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
