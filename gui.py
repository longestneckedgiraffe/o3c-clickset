import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import download_firmware
import flash_firmware
import patch_firmware
import set_counts

PAD = 8
BACKUP_FILE = "counts_backup.txt"
MUTED = "#666"
ERROR = "#b00020"

status = None
progress = None
output = None


def set_status(message):
    status.set(message)


def log(text, warn=False):
    output["state"] = "normal"
    output.insert("end", text + "\n", ("warn",) if warn else ())
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
        set_status("Ready")
        if err is not None:
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
    return f"left {vals[0]}     middle {vals[1]}     right {vals[2]}     (slot4 {vals[3]})"


def pick_into(entry):
    path = filedialog.askopenfilename(title="Select firmware image")
    if path:
        entry.delete(0, "end")
        entry.insert(0, path)


def build_download(parent):
    f = ttk.LabelFrame(parent, text="Download firmware", padding=PAD)
    f.pack(fill="x", padx=PAD, pady=(PAD, 4))
    f.columnconfigure(0, weight=1)

    out = ttk.Entry(f)
    out.insert(0, "app_O3C.bin")
    out.grid(row=0, column=0, sticky="we", padx=(0, 6))
    btn = ttk.Button(f, text="Download", width=18)
    btn.grid(row=0, column=1)

    def done(res):
        n, ok = res
        log(f"Saved {n:,} bytes.     Verified: {'yes' if ok else 'no'}", warn=not ok)

    btn.configure(command=lambda: run_async(
        btn, "Downloading firmware...",
        lambda: download_firmware.download(out.get()), done))


def build_patch(parent):
    f = ttk.LabelFrame(parent, text="Patch firmware", padding=PAD)
    f.pack(fill="x", padx=PAD, pady=4)
    f.columnconfigure(1, weight=1)

    ttk.Label(f, text="Stock image").grid(row=0, column=0, sticky="w", padx=(0, 8))
    stock = ttk.Entry(f)
    stock.grid(row=0, column=1, sticky="we", padx=(0, 6))
    ttk.Button(f, text="Browse", width=10, command=lambda: pick_into(stock)).grid(row=0, column=2)

    ttk.Label(f, text="Output").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
    out = ttk.Entry(f)
    out.grid(row=1, column=1, sticky="we", padx=(0, 6), pady=(6, 0))

    btn = ttk.Button(f, text="Build patched image")
    btn.grid(row=2, column=1, sticky="w", pady=(8, 0))

    def work():
        if not stock.get().strip():
            raise SystemExit("Choose a stock firmware image first.")
        return patch_firmware.build_patched(stock.get(), out.get().strip() or None)

    def done(res):
        o, b, n, ok = res
        log(f"Patched: {o}\nBackup:  {b}\nVerified: {'yes' if ok else 'no'}     ({n:,} bytes)", warn=not ok)

    btn.configure(command=lambda: run_async(btn, "Building patched image...", work, done))


def build_flash(parent):
    f = ttk.LabelFrame(parent, text="Flash firmware", padding=PAD)
    f.pack(fill="x", padx=PAD, pady=4)
    f.columnconfigure(1, weight=1)

    ttk.Label(f, text="Image").grid(row=0, column=0, sticky="w", padx=(0, 8))
    img = ttk.Entry(f)
    img.insert(0, "app_O3C_clickset.bin")
    img.grid(row=0, column=1, sticky="we", padx=(0, 6))
    ttk.Button(f, text="Browse", width=10, command=lambda: pick_into(img)).grid(row=0, column=2)

    ttk.Label(f, text="Put the device in bootloader mode first (hold the knob 2-3s, or Jump to bootloader). "
                      "o3cpatch downloads automatically on first use. Do not unplug while flashing.",
              foreground=MUTED, wraplength=520, justify="left").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    btn = ttk.Button(f, text="Flash")
    btn.grid(row=2, column=1, sticky="w", pady=(8, 0))

    def work():
        if not img.get().strip():
            raise SystemExit("Choose a firmware image to flash.")
        line = lambda s: btn.after(0, lambda: log(s))
        return flash_firmware.flash(img.get().strip(), on_line=line, gui=True)

    def done(code):
        log("Flash complete." if code == 0 else f"Flash finished with code {code} (see output).", warn=code != 0)

    def go():
        if not messagebox.askyesno(
                "Flash firmware",
                "This overwrites the device firmware using o3cpatch's upgrade.exe.\n\n"
                "Is the device in bootloader mode (hold the knob 2-3s, or Jump to bootloader)?\n"
                "Do not unplug during flashing.\n\nContinue?"):
            set_status("Flash cancelled")
            return
        run_async(btn, "Flashing firmware...", work, done)

    btn.configure(command=go)


def build_counts(parent):
    f = ttk.LabelFrame(parent, text="Key press counts", padding=PAD)
    f.pack(fill="x", padx=PAD, pady=4)

    fields = ttk.Frame(f)
    fields.grid(row=0, column=0, sticky="w")
    entries = {}
    for i, k in enumerate(set_counts.KEYS):
        ttk.Label(fields, text=k.capitalize()).grid(row=0, column=2 * i, sticky="e", padx=(0 if i == 0 else 16, 4))
        e = ttk.Entry(fields, width=12)
        e.grid(row=0, column=2 * i + 1)
        entries[k] = e

    ttk.Label(f, text="Leave a field blank to keep its current value.", foreground=MUTED).grid(
        row=1, column=0, sticky="w", pady=(4, 0))

    buttons = ttk.Frame(f)
    buttons.grid(row=2, column=0, sticky="w", pady=(8, 0))
    read_btn = ttk.Button(buttons, text="Read", width=12)
    read_btn.grid(row=0, column=0, padx=(0, 6))
    write_btn = ttk.Button(buttons, text="Write", width=12)
    write_btn.grid(row=0, column=1)

    def show_current(vals):
        log("Current:  " + fmt_counts(vals))

    read_btn.configure(command=lambda: run_async(
        read_btn, "Reading counts...", lambda: with_device(set_counts.read_counts), show_current))

    def do_write():
        wanted = {}
        for k in set_counts.KEYS:
            s = entries[k].get().strip()
            if not s:
                wanted[k] = None
                continue
            try:
                v = int(s)
            except ValueError:
                messagebox.showerror("Error", f"{k.capitalize()} must be a whole number.")
                return
            if not (0 <= v <= 0xFFFFFFFF):
                messagebox.showerror("Error", "Counts must be 0 .. 4294967295.")
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
            with open(BACKUP_FILE, "w") as fh:
                fh.write(f"left={current[0]} middle={current[1]} right={current[2]} slot4={current[3]}\n")
            new = list(current)
            for i, k in enumerate(set_counts.KEYS):
                if wanted[k] is not None:
                    new[i] = wanted[k]

            def after_write(res):
                _, after = res
                if after[:3] == new[:3]:
                    log("Current:  " + fmt_counts(after))
                    log(f"Counts written. Backup saved to {BACKUP_FILE}")
                    set_status(f"Counts written. Backup saved to {BACKUP_FILE}")
                else:
                    log("Current:  " + fmt_counts(after) + "  (readback mismatch)", warn=True)
                    set_status("Readback mismatch")
                    messagebox.showwarning(
                        "Readback mismatch",
                        "The values read back do not match what was written.\n"
                        "Key presses between write and read can cause this.")

            run_async(write_btn, "Writing counts...", lambda: with_device(
                lambda dev: (set_counts.write_counts(dev, new), set_counts.read_counts(dev))), after_write)

        run_async(write_btn, "Reading counts...", lambda: with_device(set_counts.read_counts), after_read)

    write_btn.configure(command=do_write)


def build_ui(root):
    global status, progress, output
    root.title("SayoDevice O3C clickset")
    root.minsize(540, 0)
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    build_download(root)
    build_patch(root)
    build_flash(root)
    build_counts(root)

    bar = ttk.Frame(root, relief="groove", padding=(PAD, 4))
    bar.pack(fill="x", side="bottom")
    status = tk.StringVar(value="Ready")
    ttk.Label(bar, textvariable=status, foreground=MUTED).pack(side="left")
    progress = ttk.Progressbar(bar, mode="determinate", length=160)
    progress.pack(side="right")

    out_frame = ttk.LabelFrame(root, text="Output", padding=(PAD, 4))
    out_frame.pack(fill="both", expand=True, padx=PAD, pady=(4, 6))
    scroll = ttk.Scrollbar(out_frame)
    scroll.pack(side="right", fill="y")
    output = tk.Text(out_frame, height=7, wrap="word", state="disabled",
                     relief="flat", background="#f6f6f6", yscrollcommand=scroll.set)
    output.pack(side="left", fill="both", expand=True)
    scroll.config(command=output.yview)
    output.tag_config("warn", foreground=ERROR)


def main():
    root = tk.Tk()
    build_ui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
