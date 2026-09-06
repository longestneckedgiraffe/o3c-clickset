import queue
import unittest
from unittest import mock

import gui


class FakeDevice:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class GuiBehaviorTests(unittest.TestCase):
    def test_callback_failure_does_not_stop_event_polling(self):
        events = queue.Queue()
        failed = mock.Mock(side_effect=RuntimeError("callback failed"))
        following = mock.Mock()
        events.put(failed)
        events.put(following)

        with mock.patch.object(gui, "ui_events", events), mock.patch.object(gui, "root") as root:
            with self.assertRaisesRegex(RuntimeError, "callback failed"):
                gui.process_ui_events()

            root.after.assert_called_once_with(25, gui.process_ui_events)
            following.assert_not_called()
            root.after.call_args.args[1]()

        following.assert_called_once_with()
        self.assertTrue(events.empty())

    def test_zero_counts_remain_classified_as_stock(self):
        device = FakeDevice()

        with mock.patch.object(gui.set_counts, "open_device", return_value=device), \
                mock.patch.object(gui.set_counts, "read_counts", return_value=[0, 0, 0, 0]):
            self.assertEqual(gui.probe_device(), ("stock", [0, 0, 0, 0]))

        self.assertTrue(device.closed)

    def test_count_parser_accepts_blank_and_unsigned_values(self):
        for text, expected in (("", None), ("  ", None), ("0", 0), ("123", 123),
                               (" 123 ", 123), ("\u0661\u0662\u0663", 123), ("4294967295", 0xFFFFFFFF)):
            with self.subTest(text=text):
                self.assertEqual(gui.parse_count(text), (expected, None))

    def test_count_parser_rejects_invalid_and_oversized_values(self):
        for text in ("-1", "+1", "1.5", "1_000", "\u00b2", "4294967296", "9" * 5000):
            with self.subTest(text=text[:20]):
                value, error = gui.parse_count(text)
                self.assertIsNone(value)
                self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
