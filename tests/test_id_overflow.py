import threading
import unittest
import os
from supernovacontroller.sequential import SupernovaDevice
from supernovacontroller.errors import DeviceOpenError

class TestSupernovaControllerIdOverflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Initializes the testing class. Determines whether to use the simulator or real device
        based on the "USE_REAL_DEVICE" environment variable. Default is to use the simulator.
        """
        cls.use_simulator = not os.getenv("USE_REAL_DEVICE", "False") == "True"

    def test_id_overflow(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        d = SupernovaDevice(start_id=65535)
        timeout = 3

        device_info = None
        device_error = None
        def open_device():
            nonlocal device_info, device_error
            try:
                device_info = d.open()
            except DeviceOpenError as e:
                device_error = e

        thread = threading.Thread(target=open_device, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            self.fail("Transaction ID over 65535 timed out")
        else:
            if isinstance(device_error, DeviceOpenError):
                self.fail(f"Failed to open device: {device_error}")
            else:
              self.assertIsNotNone(device_info, "device_info is None")

if __name__ == "__main__":
    unittest.main()
