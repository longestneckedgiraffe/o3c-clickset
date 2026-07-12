import argparse
import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

O3CPATCH_ZIP = "https://github.com/Vali0004/o3cpatch/archive/refs/heads/main.zip"
DEFAULT_ROOT = "o3cpatch"
FIRMWARE_NAME = "app_O3C.bin"


def ensure_o3cpatch(root=DEFAULT_ROOT, on_line=print):
    upgrade = os.path.join(root, "tools", "upgrade.exe")
    if os.path.exists(upgrade):
        return root
    on_line(f"Downloading o3cpatch from {O3CPATCH_ZIP}")
    with urllib.request.urlopen(O3CPATCH_ZIP, timeout=120) as r:
        data = r.read()
    on_line(f"Extracting {len(data):,} bytes")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        top = z.namelist()[0].split("/")[0]
        z.extractall(".")
    if os.path.abspath(top) != os.path.abspath(root):
        if os.path.exists(root):
            shutil.rmtree(root)
        os.rename(top, root)
    if not os.path.exists(upgrade):
        raise SystemExit("o3cpatch downloaded but tools/upgrade.exe is missing")
    on_line(f"o3cpatch ready at {root}")
    return root


def flash(image_path, root=DEFAULT_ROOT, firmware_name=FIRMWARE_NAME, on_line=print, gui=False):
    if sys.platform != "win32":
        raise SystemExit("Flashing uses o3cpatch's upgrade.exe and only runs on Windows.")
    if not os.path.exists(image_path):
        raise SystemExit(f"Image not found: {image_path}")

    root = ensure_o3cpatch(root, on_line)
    target = os.path.join(root, "firmware", firmware_name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copyfile(image_path, target)
    on_line(f"Staged {os.path.basename(image_path)} -> {target}")

    upgrade = os.path.join(root, "tools", "upgrade.exe")
    flags = subprocess.CREATE_NEW_CONSOLE if gui else 0
    on_line("Launching upgrade.exe in a new console. Follow its prompts; do not unplug!"
            if gui else "Running upgrade.exe -r (do not unplug)")
    code = subprocess.run([upgrade, "-r"], cwd=root, creationflags=flags).returncode
    on_line(f"upgrade.exe exited with code {code}")
    return code


def main():
    ap = argparse.ArgumentParser(description="Flash a (patched) O3C firmware image using o3cpatch's upgrade.exe")
    ap.add_argument("image", nargs="?", default="app_O3C_clickset.bin", help="firmware image to flash")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="o3cpatch folder (auto-downloaded if missing)")
    ap.add_argument("--firmware-name", default=FIRMWARE_NAME, help="target filename under o3cpatch/firmware/")
    args = ap.parse_args()

    sys.exit(flash(args.image, root=args.root, firmware_name=args.firmware_name))


if __name__ == "__main__":
    main()
