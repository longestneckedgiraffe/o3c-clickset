import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import build_patch
import download_firmware
import o3c_fw
import patch_firmware
import set_counts


def with_device(fn):
    dev = set_counts.open_device()
    try:
        return fn(dev)
    finally:
        dev.close()


def fmt_counts(label, vals):
    return f"{label}: left={vals[0]} middle={vals[1]} right={vals[2]} (slot4={vals[3]})"


def run_async(button, work, on_done):
    button["state"] = "disabled"

    def finish(result, err):
        button["state"] = "normal"
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


def section(parent, title):
    f = ttk.LabelFrame(parent, text=title, padding=8)
    f.pack(fill="x", padx=10, pady=6)
    f.columnconfigure(1, weight=1)
    return f


def pick_into(entry):
    path = filedialog.askopenfilename(title="Select firmware image")
    if path:
        entry.delete(0, "end")
        entry.insert(0, path)


def build_download(parent):
    f = section(parent, "1. Download firmware")
    ttk.Label(f, text="Output file:").grid(row=0, column=0, sticky="w")
    out = ttk.Entry(f)
    out.insert(0, "app_O3C.bin")
    out.grid(row=0, column=1, sticky="we", padx=6)
    result = tk.StringVar()
    btn = ttk.Button(f, text="Download")
    btn.grid(row=0, column=2, padx=4)

    def done(res):
        n, ok = res
        msg = f"Downloaded {n} bytes -> {out.get()}\nVerification: {ok}"
        if not ok:
            msg += "\nWARNING: Image failed verification"
        result.set(msg)

    btn.configure(command=lambda: run_async(btn, lambda: download_firmware.download(out.get()), done))
    ttk.Label(f, textvariable=result, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))


def build_patch_section(parent):
    f = section(parent, "2. Patch firmware")
    ttk.Label(f, text="Stock image:").grid(row=0, column=0, sticky="w")
    stock = ttk.Entry(f)
    stock.grid(row=0, column=1, sticky="we", padx=6)
    ttk.Button(f, text="Browse...", command=lambda: pick_into(stock)).grid(row=0, column=2, padx=4)

    ttk.Label(f, text="Output (blank = auto):").grid(row=1, column=0, sticky="w")
    out = ttk.Entry(f)
    out.grid(row=1, column=1, sticky="we", padx=6)
    ttk.Label(f, text="Backup (blank = auto):").grid(row=2, column=0, sticky="w")
    backup = ttk.Entry(f)
    backup.grid(row=2, column=1, sticky="we", padx=6)

    result = tk.StringVar()
    btn = ttk.Button(f, text="Build patched image")
    btn.grid(row=3, column=1, sticky="w", pady=6)

    def work():
        if not stock.get().strip():
            raise SystemExit("Choose a stock firmware image first.")
        return patch_firmware.build_patched(stock.get(), out.get().strip() or None, backup.get().strip() or None)

    def done(res):
        o, b, n, ok = res
        result.set(
            f"Patched image : {o} {n} bytes\n"
            f"Stock backup  : {b}\n"
            f"MD5 Verifies  : {ok}\n"
            f"Magic         : 0x{build_patch.MAGIC:08X}\n"
            f"stub @ VA 0x{build_patch.STUB:X} (file 0x{build_patch.STUB - o3c_fw.LOAD_ADDR:X}), hook @ VA 0x8508")

    btn.configure(command=lambda: run_async(btn, work, done))
    ttk.Label(f, textvariable=result, justify="left", font=("Courier New", 9)).grid(
        row=4, column=0, columnspan=3, sticky="w")


def build_read(parent):
    f = section(parent, "3. Read counts")
    result = tk.StringVar()
    btn = ttk.Button(f, text="Read counts")
    btn.grid(row=0, column=0, sticky="w")
    btn.configure(command=lambda: run_async(
        btn, lambda: with_device(set_counts.read_counts),
        lambda vals: result.set(fmt_counts("current", vals))))
    ttk.Label(f, textvariable=result, justify="left").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))


def build_set(parent):
    f = section(parent, "4. Set counts")
    entries = {}
    for i, k in enumerate(set_counts.KEYS):
        ttk.Label(f, text=f"{k}:").grid(row=0, column=2 * i, sticky="e")
        e = ttk.Entry(f, width=12)
        e.grid(row=0, column=2 * i + 1, padx=(2, 10))
        entries[k] = e
    ttk.Label(f, text="(blank = keep current)").grid(row=1, column=0, columnspan=6, sticky="w")

    ttk.Label(f, text="Backup file:").grid(row=2, column=0, sticky="e")
    backup = ttk.Entry(f, width=24)
    backup.insert(0, "counts_backup.txt")
    backup.grid(row=2, column=1, columnspan=3, sticky="w", padx=2, pady=4)

    result = tk.StringVar()
    btn = ttk.Button(f, text="Write counts")
    btn.grid(row=3, column=0, sticky="w", pady=4)
    ttk.Label(f, textvariable=result, justify="left").grid(row=4, column=0, columnspan=6, sticky="w")

    def do_set():
        wanted = {}
        for k in set_counts.KEYS:
            s = entries[k].get().strip()
            if not s:
                wanted[k] = None
                continue
            try:
                v = int(s)
            except ValueError:
                messagebox.showerror("Error", f"{k} must be a whole number")
                return
            if not (0 <= v <= 0xFFFFFFFF):
                messagebox.showerror("Error", "Counts must be 0 .. 4294967295")
                return
            wanted[k] = v

        def after_read(current):
            result.set(fmt_counts("current", current))
            if not messagebox.askyesno(
                    "Safety check",
                    "The 'current' values shown above must match the all-time counts on your "
                    "device screen.\n\nIf they do NOT match, choose No to abort.\n\nDo they match?"):
                result.set("Aborted")
                return
            with open(backup.get(), "w") as fh:
                fh.write(f"left={current[0]} middle={current[1]} right={current[2]} slot4={current[3]}\n")
            new = list(current)
            for i, k in enumerate(set_counts.KEYS):
                if wanted[k] is not None:
                    new[i] = wanted[k]

            def after_write(res):
                prev, after = res
                lines = [f"Backup saved to {backup.get()}", fmt_counts("writing", new)]
                if prev[:3] != current[:3]:
                    lines.append("Note: pre-write snapshot differs from first read")
                lines.append(fmt_counts("readback", after))
                lines.append("OK" if after[:3] == new[:3] else "WARNING: readback does not match")
                result.set("\n".join(lines))

            run_async(btn, lambda: with_device(
                lambda dev: (set_counts.write_counts(dev, new), set_counts.read_counts(dev))), after_write)

        run_async(btn, lambda: with_device(set_counts.read_counts), after_read)

    btn.configure(command=do_set)


def main():
    root = tk.Tk()
    root.title("SayoDevice O3C clickset")
    build_download(root)
    build_patch_section(root)
    ttk.Label(root, text="Then flash the patched image with SayoDevice's flasher, then read or set counts below.",
              wraplength=470, foreground="#555").pack(fill="x", padx=12, pady=(0, 2))
    build_read(root)
    build_set(root)
    root.mainloop()


if __name__ == "__main__":
    main()
