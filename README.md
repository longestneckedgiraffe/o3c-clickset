# o3c-clickset

Patches SayoDevice O3C firmware 1.4.12 to add a click-counter command, then reads and sets the device's all-time key press counts over USB HID.

> [!CAUTION]
> This flashes custom firmware and writes directly to your device over USB HID. It only works on SayoDevice O3C firmware 1.4.12, and writing counts is irreversible. Back up your factory counts before modifying and use at your own risk!

## Install

First, install [Git](https://git-scm.com/downloads) and [Python](https://www.python.org/downloads/) if you don't already have them. Then:

```sh
git clone https://github.com/longestneckedgiraffe/o3c-clickset.git
cd o3c-clickset
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### GUI

```sh
.venv\Scripts\python.exe gui.py
```
or (equivalent)

```sh
run.bat
```

Then, in the window:

1. Click **Download** to fetch the stock firmware from SayoDevice's CDN.
2. In **Patch**, pick `app_O3c.bin` and press **Build** to produce the patched `app_O3C_clickset.bin`.
3. Click **Flash**. The flashing utility automatically puts the device in bootloader mode; do not unplug it during flashing.
4. Once the patched firmware is on the device, in **Counts** click **Read** to show the current values, type the new counts, and click **Write** to write the values.
5. Optionally, flash back the stock 1.4.12 on [sayodevice.com](https://sayodevice.com).

### CLI

```sh
python download_firmware.py
python patch_firmware.py app_O3C.bin
python flash_firmware.py app_O3C_clickset.bin
python set_counts.py read
python set_counts.py set --left n --middle n --right n
```

## Architecture

- [IDA Pro](https://hex-rays.com/ida-pro) 9.3 was used to analyze the stock firmware and obtain the necessary information to create the patcher. Future updates will likely require using a similar [disassembler](https://en.wikipedia.org/wiki/Disassembler).

## FAQ

**Can this brick or destroy my SayoDevice?**

No. The flashing utility and this application never touch the bootloader. If anything goes wrong, you can easily reflash stock firmware at [sayodevice.com](https://sayodevice.com).

**Will my settings change or get overridden?**

No. Your settings (actuation, lighting, etc) are not affected by the firmware flashing.

**Is the binary patching version independent?**

No. The patch targets a specific firmware version. The downloader always fetches the latest version, which as of now is 1.4.12. If the latest version ever changes, this project is broken until it's updated and the patching utility will fail.

**Are these changes permanent?**

Yes. Once the custom firmware is flashed and a count is written over HID, it is irreversible. If you want to keep your factory counts, store them somewhere before modifying and write them back afterward. You can safely overwrite the firmware later by reflashing the latest version on [sayodevice.com](https://sayodevice.com); the counts persist.

**Why isn't it working?**

The most common issues are:

- You're device is not on firmware version 1.4.12.
- You're not displaying lifetime counts on your device.
  - Hold the knob, go to **Display** -> **Main screen**, and set **Key count** to **ALL**, which shows lifetime presses.
- Your Sayodevice O3C is not plugged in.
- This project is out of date.

## Attribution

- [o3cpatch](https://github.com/Vali0004/o3cpatch)
  - o3cpatch is automatically downloaded and used in this project to flash the firmware.

## License

[MIT](LICENSE.md)
