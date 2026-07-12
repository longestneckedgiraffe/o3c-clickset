import tempfile
import unittest
from pathlib import Path
from unittest import mock

import file_utils


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_write_replaces_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory, "output.bin")
            destination.write_bytes(b"old")

            file_utils.atomic_write_bytes(destination, b"new")

            self.assertEqual(destination.read_bytes(), b"new")

    def test_failed_replace_preserves_destination_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory, "output.bin")
            destination.write_bytes(b"old")

            with mock.patch.object(file_utils.os, "replace", side_effect=OSError("failed")):
                with self.assertRaises(OSError):
                    file_utils.atomic_write_bytes(destination, b"new")

            self.assertEqual(destination.read_bytes(), b"old")
            self.assertEqual(list(Path(directory).glob(".output.bin.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
