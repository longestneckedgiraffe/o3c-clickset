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
        self.assertEqual(gui.parse_count(""), (None, None))
        self.assertEqual(gui.parse_count("123"), (123, None))
        self.assertIsNotNone(gui.parse_count("-1")[1])


if __name__ == "__main__":
    unittest.main()
