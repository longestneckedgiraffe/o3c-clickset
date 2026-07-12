import struct
import tempfile
import unittest
from pathlib import Path

import set_counts


def response(values):
    report = bytearray(set_counts.REPORT_LEN)
    report[0] = set_counts.REPORT_ID
    struct.pack_into("<4I", report, set_counts.RESP_OFF, *values)
    return list(report)


class FakeDevice:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, length, timeout_ms):
        return self.responses.pop(0)


class CountWorkflowTests(unittest.TestCase):
    def test_update_counts_reads_backs_up_writes_and_reads_back(self):
        current = (1, 2, 3, 4)
        wanted = (5, 2, 3, 4)
        device = FakeDevice((response(current), response(current), response(wanted)))

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory, "counts.txt")
            result = set_counts.update_counts(device, {"left": 5}, backup)

            self.assertEqual(result, (list(current), list(wanted), list(current), list(wanted)))
            self.assertEqual(backup.read_text(), "left=1 middle=2 right=3 slot4=4\n")
            self.assertEqual(len(device.writes), 3)

    def test_invalid_response_raises_domain_error(self):
        device = FakeDevice(([set_counts.REPORT_ID],))

        with self.assertRaises(set_counts.DeviceResponseError):
            set_counts.read_counts(device)

    def test_invalid_count_is_rejected_before_write(self):
        with self.assertRaises(set_counts.CountValueError):
            set_counts.merge_counts([1, 2, 3, 4], {"left": -1})


if __name__ == "__main__":
    unittest.main()
