import hashlib
import io
import os
import unittest
import zipfile
from unittest import mock

import flash_firmware


def make_archive(prefix, files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, contents in files.items():
            archive.writestr(prefix + name, contents)
    return data.getvalue()


class TemporaryO3cpatchTests(unittest.TestCase):
    def test_verified_files_are_removed_after_use(self):
        prefix = "fixture/"
        files = {
            "tools/upgrade.exe": b"upgrade",
            "config.json": b"config",
            "LICENSE": b"license",
        }
        hashes = {name: hashlib.sha256(contents).hexdigest() for name, contents in files.items()}
        archive = make_archive(prefix, files)

        with mock.patch.object(flash_firmware, "O3CPATCH_PREFIX", prefix), \
                mock.patch.object(flash_firmware, "O3CPATCH_FILES", hashes), \
                mock.patch.object(flash_firmware.urllib.request, "urlopen", return_value=io.BytesIO(archive)):
            with flash_firmware.temporary_o3cpatch(lambda message: None) as root:
                saved_root = root
                for relative in files:
                    self.assertTrue(os.path.isfile(os.path.join(root, *relative.split("/"))))

        self.assertFalse(os.path.exists(saved_root))

    def test_hash_mismatch_is_rejected(self):
        prefix = "fixture/"
        files = {"tools/upgrade.exe": b"unexpected"}
        archive = make_archive(prefix, files)

        with mock.patch.object(flash_firmware, "O3CPATCH_PREFIX", prefix), \
                mock.patch.object(flash_firmware, "O3CPATCH_FILES", {"tools/upgrade.exe": "0" * 64}), \
                mock.patch.object(flash_firmware.urllib.request, "urlopen", return_value=io.BytesIO(archive)):
            with self.assertRaises(SystemExit):
                with flash_firmware.temporary_o3cpatch(lambda message: None):
                    pass


if __name__ == "__main__":
    unittest.main()
