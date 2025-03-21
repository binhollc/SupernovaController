import sys
import os
import unittest
from threading import Event
from unittest import mock
from supernovacontroller.sequential import SupernovaDevice
from supernovacontroller.sequential.i3c import SupernovaI3CBlockingInterface

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binhosimulators import BinhoSupernovaSimulator

counter = 0
last_ibi = Event()
caught_ibis = []

def _is_ibi(name, message):
        return message["name"].strip() == "I3C IBI NOTIFICATION" and message["header"]["type"] == "IBI_NORMAL"

def _handle_ibi(name, message):
    global counter
    global last_ibi
    global caught_ibis

    caught_ibis.append({"dynamic_address": message["header"]["address"],  "controller_response": message["header"]["response"], "mdb":message["payload"][0]})

    counter += 1
    if counter == 5:
        last_ibi.set()

BMM350_PID_DATA = {"asString": ["0x07", "0x70", "0x10", "0x33", "0x00", "0x00"], "asInt": [7, 112, 16, 51, 0, 0]}
BMI323_PID_DATA = {"asString": ["0x07", "0x70", "0x10", "0x43", "0x10", "0x00"], "asInt": [7, 112, 16, 67, 16, 0]}

class TestI3CSupernovaController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Initializes the testing class. Determines whether to use the simulator or real device
        based on the "USE_REAL_DEVICE" environment variable. Default is to use the simulator.
        """
        cls.use_simulator = not os.getenv("USE_REAL_DEVICE", "False") == "True"

    def setUp(self):
        self.device = SupernovaDevice()

        if self.use_simulator:
            self.device.driver = BinhoSupernovaSimulator()

        self.device_info = self.device.open()
        self.i3c : SupernovaI3CBlockingInterface = self.device.create_interface("i3c.controller")

    def tearDown(self):
        global caught_ibis
        global last_ibi
        global counter

        counter = 0
        caught_ibis.clear()
        last_ibi.clear()
        self.device.close()
        
    def test_set_i3c_bus_voltage_attribute(self):
        (success, result) = self.i3c.set_bus_voltage(3300)

        self.assertTupleEqual((success, result), (True, 3300))
        self.assertEqual(self.i3c.bus_voltage, 3300)

    def test_set_i3c_frequencies(self):
        (success, result) = self.i3c.set_parameters(
            self.i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ,
            self.i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ
        )

        self.assertEqual((success, result), (True, (self.i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ, self.i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ)))

    def test_i3c_frequencies_should_take_default_values_if_not_set(self):
        (success, result) = self.i3c.get_parameters()

        self.assertEqual((success, result), (True, (self.i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ, self.i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ)))

    def test_set_i3c_bus_voltage_attribute_error(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")
        # Mock the controller's sync_submit method to simulate a failure response.
        # It's important to note that this approach makes the test somewhat dependent
        # on the internal implementation of the device class.
        with mock.patch.object(self.device.controller, "sync_submit") as mock_sync_submit:
            mock_sync_submit.return_value = [{"name": "SET I3C BUS VOLTAGE", "result": 1}]  # Simulate an error response

            # Call the method under test
            (success, result) = self.i3c.set_bus_voltage(3300)

            # Assert that the method correctly returns an error
            self.assertTupleEqual((success, result), (False, "Set bus voltage failed"))
            self.assertEqual(self.i3c.bus_voltage, None)

    def test_i3c_init_bus_with_no_targets_connected(self):
        # This test assumes that the are no devices connected to the bus.

        if self.use_simulator:
            self.skipTest("For real device only")

        (success, result) = self.i3c.init_bus(1500)

        self.assertEqual(success, False, "Init bus succeded, are there devices connected?")
        self.assertDictEqual(result, {"errors": "RSTDAA_FAILED"}, f"Got unexpected result: {result}")

    def test_i3c_reset_bus(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.i3c.init_bus(2000)
        (success, result) = self.i3c.reset_bus()

        self.assertTupleEqual((success, result), (True, 2000))

    def test_i3c_reset_bus_before_init(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        (success, _) = self.i3c.reset_bus()

        self.assertEqual(success, True)

    def test_i3c_targets(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.i3c.init_bus(3300)
        (success, targets) = self.i3c.targets()

        self.assertEqual(success, True)
        self.assertEqual(len(targets), 3)
        self.assertDictEqual(targets[0], {
            "static_address": 0x50,
            "dynamic_address": 0x08,
            "bcr": 0x10,
            "dcr": 0xC3,
            "pid": ["0x00", "0x00", "0x00", "0x00", "0x64", "0x65"],
        })
        self.assertDictEqual(targets[1], {
            "static_address": 0x51,
            "dynamic_address": 0x09,
            "bcr": 0x03,
            "dcr": 0x63,
            "pid": ["0x02", "0x17", "0x0F", "0x1D", "0x00", "0x5A"],
        })
        self.assertDictEqual(targets[2], {
            "static_address": 0x52,
            "dynamic_address": 0x0A,
            "bcr": 0x10,
            "dcr": 0xC3,
            "pid": ["0x06", "0x06", "0x06", "0x06", "0x66", "0x66"],
        })

    def test_i3c_targets_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        (success, targets) = self.i3c.targets()

        self.assertTupleEqual((success, targets), (True, []))

    def test_i3c_write_operation_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        (success, _) = self.i3c.write(
            0x08,
            self.i3c.TransferMode.I3C_SDR,
            [0x00, 0x00],
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        self.assertEqual(success, False)

    def test_i3c_read_operation_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        (success, _) = self.i3c.read(
            0x08,
            self.i3c.TransferMode.I3C_SDR,
            [0x00, 0x00],
            1
        )

        self.assertEqual(success, False)

    def test_i3c_write_on_target_should_return_none(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.i3c.init_bus(3300)

        subaddress = [0x00, 0x00]

        (success, result) = self.i3c.write(
            0x08,
            self.i3c.TransferMode.I3C_SDR,
            subaddress,
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        self.assertTupleEqual((success, result), (True, None))

    def test_i3c_successful_write_read_operations_on_target(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.i3c.init_bus(3300)

        subaddress = [0x00, 0x00]

        (success, result) = self.i3c.write(
            0x08,
            self.i3c.TransferMode.I3C_SDR,
            subaddress,
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        (success, result) = self.i3c.read(
            0x08,
            self.i3c.TransferMode.I3C_SDR,
            subaddress,
            4
        )

        self.assertTupleEqual((success, result), (True, [0xDE, 0xAD, 0xBE, 0xEF]))
        
    def test_toggle_handle_ibi(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")
        
        self.device.on_notification(name="ibi", filter_func=_is_ibi, handler_func=_handle_ibi)

        self.i3c.init_bus(3300)

        (success, _) = self.i3c.toggle_ibi(0x0A, True)

        self.assertEqual(success, True)

        last_ibi.wait()

        (success, _) = self.i3c.toggle_ibi(0x0A, False)

        self.assertEqual(success, True)

        self.assertEqual(len(caught_ibis), 5)
        for ibi in caught_ibis:
            self.assertDictEqual({"dynamic_address": 10, "controller_response": "IBI_ACKED_WITH_PAYLOAD", "mdb": 2}, ibi)

    def test_find_target_by_pid_with_BMI323(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i3c.init_bus(3300)

        target_pid = ["0x07", "0x70", "0x10", "0x43", "0x10", "0x00"]
        (deviceFound, bmi_device) = self.i3c.find_target_device_by_pid(target_pid)

        self.assertEqual(True, deviceFound, "Failed to find BMI323, is it connected?")
        self.assertDictContainsSubset({"bcr": 6, "dcr": 239, "pid": ["0x07", "0x70", "0x10", "0x43", "0x10", "0x00"]}, bmi_device, "Failed to find BMI323, is it connected?")

    def test_toggle_handle_ibi_BMI323(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        
        self.device.on_notification(name="ibi", filter_func=_is_ibi, handler_func=_handle_ibi)

        self.i3c.init_bus(3300)
        
        (deviceFound, bmi323) = self.i3c.find_target_device_by_pid(BMI323_PID_DATA["asString"])
        if not deviceFound:
            self.skipTest("For BMI323")

        target_address = bmi323["dynamic_address"]

        self.i3c.toggle_ibi(target_address, False)

        self.i3c.write(target_address, self.i3c.TransferMode.I3C_SDR, [0x20], [0x85, 0x40])
        self.i3c.write(target_address, self.i3c.TransferMode.I3C_SDR, [0x21], [0x95, 0x40])
        self.i3c.write(target_address, self.i3c.TransferMode.I3C_SDR, [0x3A], [0x00, 0x00])
        self.i3c.write(target_address, self.i3c.TransferMode.I3C_SDR, [0x3B], [0x00, 0x0C])
        self.i3c.write(target_address, self.i3c.TransferMode.I3C_SDR, [0x38], [0x05, 0x05])

        self.i3c.toggle_ibi(target_address, True)

        last_ibi.wait()

        (success, _) = self.i3c.toggle_ibi(target_address, False)

        self.assertEqual(success, True)

        self.assertEqual(len(caught_ibis), 5)
        for ibi in caught_ibis:
            self.assertDictEqual({"dynamic_address": target_address, "controller_response": "IBI_ACKED_WITH_PAYLOAD", "mdb": 2}, ibi)

    def test_trigger_target_reset_pattern(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        (success, result) = i3c.trigger_target_reset_pattern()

        self.assertTupleEqual((success, result), (True, None))

if __name__ == "__main__":
    unittest.main()