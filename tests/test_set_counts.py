import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
    def test_transaction_reads_response_despite_wall_clock_adjustments(self):
        expected = response((1, 2, 3, 4))
        for adjusted_time in (900.0, 1002.0):
            with self.subTest(adjusted_time=adjusted_time):
                device = mock.Mock()
                device.read.side_effect = [[], expected]

                with mock.patch.object(set_counts.time, "time", side_effect=[1000.0, adjusted_time, adjusted_time]), \
                        mock.patch.object(set_counts.time, "monotonic", side_effect=[0.0, 0.1, 0.2]):
                    result = set_counts.transact(device, set_counts.packet(0, (0, 0, 0, 0)))

                self.assertEqual(result, expected)

    def test_transaction_times_out_when_wall_clock_stops(self):
        device = mock.Mock()
        device.read.side_effect = [[], []]

        with mock.patch.object(set_counts.time, "time", return_value=1000.0), \
                mock.patch.object(set_counts.time, "monotonic", side_effect=[0.0, 0.2, 0.8, 1.0]):
            result = set_counts.transact(device, set_counts.packet(0, (0, 0, 0, 0)))

        self.assertEqual(result, [])
        self.assertEqual(device.read.call_count, 2)

    def test_device_is_closed_when_initialization_fails(self):
        candidates = [{"usage_page": set_counts.USAGE_PAGE, "path": b"device"}]
        for method in ("open_path", "set_nonblocking"):
            with self.subTest(method=method):
                device = mock.Mock()
                error = OSError("device initialization failed")
                getattr(device, method).side_effect = error

                with mock.patch.object(set_counts.hid, "enumerate", return_value=candidates), \
                        mock.patch.object(set_counts.hid, "device", return_value=device):
                    with self.assertRaises(OSError) as raised:
                        set_counts.open_device()

                self.assertIs(raised.exception, error)
                device.close.assert_called_once_with()

    def test_initialized_device_remains_open_for_caller(self):
        candidates = [{"usage_page": set_counts.USAGE_PAGE, "path": b"device"}]
        device = mock.Mock()

        with mock.patch.object(set_counts.hid, "enumerate", return_value=candidates), \
                mock.patch.object(set_counts.hid, "device", return_value=device):
            self.assertIs(set_counts.open_device(), device)

        device.open_path.assert_called_once_with(b"device")
        device.set_nonblocking.assert_called_once_with(0)
        device.close.assert_not_called()

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
