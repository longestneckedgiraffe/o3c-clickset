import argparse
import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

O3CPATCH_COMMIT = "6a1ea2735d061c9fccefd6028dfc4f846dd10488"
O3CPATCH_ZIP = f"https://github.com/Vali0004/o3cpatch/archive/{O3CPATCH_COMMIT}.zip"
O3CPATCH_PREFIX = f"o3cpatch-{O3CPATCH_COMMIT}/"
O3CPATCH_MAX_BYTES = 16 * 1024 * 1024
O3CPATCH_FILES = {
    "tools/upgrade.exe": "766849c7469f2886833831dd552ee02a977a4ef661d7c2df3b5df2030d004774",
    "config.json": "dd4544a6f1d9a4ffb881049e6a56e53f138bb463ff1cfb6fa94bf2dd8d7d9c91",
    "LICENSE": "93435e350c35fb0849a145869f26d86e81d4afecf2cc6d7c8c2802142f3d3449",
}
FIRMWARE_NAME = "app_O3C.bin"


@contextlib.contextmanager
def temporary_o3cpatch(on_line=print):
    on_line(f"Downloading o3cpatch from {O3CPATCH_ZIP}")
    with urllib.request.urlopen(O3CPATCH_ZIP, timeout=120) as r:
        data = r.read(O3CPATCH_MAX_BYTES + 1)
    if len(data) > O3CPATCH_MAX_BYTES:
        raise SystemExit("o3cpatch download exceeds the expected size")

    with tempfile.TemporaryDirectory(prefix="o3c-clickset-") as root:
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise SystemExit("o3cpatch download is not a valid ZIP archive") from e
        with archive:
            for relative, expected_hash in O3CPATCH_FILES.items():
                member = O3CPATCH_PREFIX + relative
                try:
                    contents = archive.read(member)
                except KeyError as e:
                    raise SystemExit(f"o3cpatch archive is missing {relative}") from e
                actual_hash = hashlib.sha256(contents).hexdigest()
                if actual_hash != expected_hash:
                    raise SystemExit(f"o3cpatch verification failed for {relative}")
                destination = os.path.join(root, *relative.split("/"))
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                with open(destination, "wb") as f:
                    f.write(contents)
        on_line(f"Verified o3cpatch commit {O3CPATCH_COMMIT[:12]}")
        try:
            yield root
        finally:
            on_line("Removed temporary o3cpatch files")


def flash(image_path, on_line=print, gui=False):
    if sys.platform != "win32":
        raise SystemExit("Flashing uses o3cpatch's upgrade.exe and only runs on Windows.")
    if not os.path.exists(image_path):
        raise SystemExit(f"Image not found: {image_path}")

    with temporary_o3cpatch(on_line) as root:
        target = os.path.join(root, "firmware", FIRMWARE_NAME)
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
    args = ap.parse_args()

    sys.exit(flash(args.image))


if __name__ == "__main__":
    main()
