import hashlib
import io
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_patch
import download_firmware
import o3c_fw
import patch_firmware


class FirmwareVerificationTests(unittest.TestCase):
    def test_internal_verification_rejects_short_and_oversized_images(self):
        self.assertFalse(o3c_fw.verify(b""))

        image = bytearray(o3c_fw.MD5_OFF + 16)
        struct.pack_into("<I", image, o3c_fw.SIZE_OFF, len(image) + 1)
        self.assertFalse(o3c_fw.verify(image))

    def test_internal_verification_accepts_consistent_image(self):
        image = bytearray(o3c_fw.MD5_OFF + 16)
        size = 32
        struct.pack_into("<I", image, o3c_fw.SIZE_OFF, size)
        image[o3c_fw.MD5_OFF:o3c_fw.MD5_OFF + 16] = hashlib.md5(image[:size]).digest()

        self.assertTrue(o3c_fw.verify(image))

    def test_patch_locations_require_expected_original_bytes(self):
        image = bytearray(o3c_fw.MD5_OFF + 16)
        struct.pack_into("<I", image, o3c_fw.SIZE_OFF, o3c_fw.MD5_OFF)
        hook = build_patch.HOOK - o3c_fw.LOAD_ADDR
        image[hook:hook + len(build_patch.DISPLACED)] = build_patch.DISPLACED

        patched = patch_firmware.apply_patches(bytes(image))
        self.assertEqual(patched[hook:hook + 4], build_patch.patches()[0][1])

        image[hook] ^= 0xFF
        with self.assertRaises(SystemExit):
            patch_firmware.apply_patches(bytes(image))

    def test_unknown_firmware_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "unknown.bin")
            path.write_bytes(b"unknown")

            with self.assertRaises(SystemExit):
                patch_firmware.load_decrypted(path)

    def test_failed_download_does_not_replace_existing_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "firmware.bin")
            path.write_bytes(b"existing")

            class Response(io.BytesIO):
                pass

            with mock.patch.object(download_firmware.urllib.request, "urlopen",
                                   return_value=Response(b"unsupported")):
                with self.assertRaises(SystemExit):
                    download_firmware.download(path)

            self.assertEqual(path.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
