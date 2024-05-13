import unittest
from unittest import mock
from unittest.mock import patch
from unittest.mock import MagicMock
import sys
import os
from transfer_controller import TransferController
from supernovacontroller.sequential import SupernovaDevice
from supernovacontroller.errors import DeviceOpenError
from supernovacontroller.errors import DeviceNotMountedError
from supernovacontroller.errors import DeviceAlreadyMountedError
from supernovacontroller.errors import UnknownInterfaceError
from supernovacontroller.errors import BackendError
from BinhoSupernova.commands.definitions import (
    SpiControllerBitOrder, SpiControllerMode, SpiControllerDataWidth,
    SpiControllerChipSelect, SpiControllerChipSelectPolarity)
from BinhoSupernova.Supernova import I3cTargetResetDefByte
from BinhoSupernova.Supernova import TransferDirection

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binhosimulators import BinhoSupernovaSimulator

class TestSupernovaController(unittest.TestCase):
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

    def test_open_device_with_wrong_address(self):
        with self.assertRaises(DeviceOpenError):
            self.device.open("whatever")

    def test_open_device_and_close(self):
        info = self.device.open()

        self.assertRegex(info["hw_version"], r"^[A-Za-z0-9]$", "Invalid hw_version format")
        self.assertRegex(info["fw_version"], r"^\d+\.\d+\.\d+$", "Invalid fw_version format")
        self.assertRegex(info["serial_number"], r"^[A-Fa-f0-9]+$", "Invalid serial_number format")
        self.assertEqual(info["manufacturer"], "Binho LLC", "Invalid manufacturer string")
        self.assertEqual(info["product_name"], "Binho Supernova", "Invalid product name")

        self.device.close()

    def test_open_device_more_than_once(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        with self.assertRaises(DeviceAlreadyMountedError):
            self.device.open()

    def test_create_interface_before_open_throws_error(self):
        with self.assertRaises(DeviceNotMountedError):
            self.device.create_interface("i3c.controller")

    def test_subsequent_calls_to_create_interface_retrieve_the_same_instance(self):
        self.device.open()

        instance_1 = self.device.create_interface("i3c.controller")
        instance_2 = self.device.create_interface("i3c.controller")

        self.assertEqual(instance_1, instance_2)

        self.device.close()

    def test_create_interface_wrong_name(self):
        self.device.open()

        with self.assertRaises(UnknownInterfaceError):
            self.device.create_interface("foo")

        self.device.close()

    def test_i2c_set_parameters(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        (success, result) = i2c.set_parameters(500000)

        self.assertEqual(success, True)
        self.assertEqual(result, (500000))

        self.device.close()

    def test_i2c_should_not_throw_error_if_bus_voltage_is_not_set(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        (success, _) = i2c.read_from(0x50, [0x00,0x00], 4)

        self.assertEqual(success, True)

        self.device.close()

    def test_i2c_set_bus_voltage_or_init_bus_are_equivalent(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        i2c.set_bus_voltage(3300)
        i2c.set_parameters(500000)

        try:
            i2c.read_from(0x50, [0x00,0x00], 1)
        except Exception as e:
            self.fail(f"I2C read raised an exception {e}")

        self.device.close()

    def test_i2c_write(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        i2c.init_bus(3300)
        i2c.set_parameters(500000)
        (success, result) = i2c.write(0x50, [0x00,0x00], [0xDE, 0xAD, 0xBE, 0xEF])

        self.assertEqual(success, True)
        self.assertEqual(result, None)

        self.device.close()

    def test_i2c_write_read_from(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        i2c.init_bus(3300)
        i2c.set_parameters(500000)

        i2c.write(0x50, [0x00,0x00], [0xDE, 0xAD, 0xBE, 0xEF])
        (success, data) = i2c.read_from(0x50, [0x00,0x00], 4)

        self.assertEqual(success, True)
        self.assertEqual(data, [0xDE, 0xAD, 0xBE, 0xEF])

        self.device.close()

    def test_i2c_write_continuous_read(self):
        self.device.open()

        i2c = self.device.create_interface("i2c")

        i2c.init_bus(3300)
        i2c.set_parameters(500000)

        i2c.write(0x50, [0x00, 0x00], [0x01, 0x02, 0x03, 0x04])
        i2c.write(0x50, [], [0x00, 0x00])
        (success, a) = i2c.read(0x50, 1)
        (success, b) = i2c.read(0x50, 1)
        (success, cd) = i2c.read(0x50, 2)

        self.assertEqual(success, True)
        self.assertEqual(a, [0x01])
        self.assertEqual(b, [0x02])
        self.assertEqual(cd, [0x03, 0x04])

        self.device.close()

    def test_set_i3c_bus_voltage_attribute(self):
        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, result) = i3c.set_bus_voltage(3300)

        self.assertTupleEqual((success, result), (True, 3300))
        self.assertEqual(i3c.bus_voltage, 3300)

        self.device.close()

    def test_set_i3c_frequencies(self):
        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, result) = i3c.set_parameters(
            i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ,
            i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ
        )

        self.assertEqual((success, result), (True, (i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ, i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ)))

        self.device.close()

    def test_i3c_frequencies_should_take_default_values_if_not_set(self):
        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, result) = i3c.get_parameters()

        self.assertEqual((success, result), (True, (i3c.I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ, i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ)))

        self.device.close()

    def test_set_i3c_bus_voltage_attribute_error(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        # Mock the controller's sync_submit method to simulate a failure response.
        # It's important to note that this approach makes the test somewhat dependent
        # on the internal implementation of the device class.
        with mock.patch.object(self.device.controller, "sync_submit") as mock_sync_submit:
            mock_sync_submit.return_value = [{"name": "SET I3C BUS VOLTAGE", "result": 1}]  # Simulate an error response

            # Call the method under test
            (success, result) = i3c.set_bus_voltage(3300)

            # Assert that the method correctly returns an error
            self.assertTupleEqual((success, result), (False, "Set bus voltage failed"))
            self.assertEqual(i3c.bus_voltage, None)

        self.device.close()

    def test_i3c_init_bus_with_no_targets_connected(self):
        # This test assumes that the are no devices connected to the bus.

        if self.use_simulator:
            self.skipTest("For real device only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, result) = i3c.init_bus(1500)

        self.assertEqual(success, False)
        self.assertTrue("errors" in result)

        self.device.close()

    def test_i3c_reset_bus(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(2000)
        (success, result) = i3c.reset_bus()

        self.assertTupleEqual((success, result), (True, 2000))

        self.device.close()

    def test_i3c_reset_bus_before_init(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, _) = i3c.reset_bus()

        self.assertEqual(success, True)

        self.device.close()

    def test_i3c_targets(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)
        (success, targets) = i3c.targets()

        self.assertEqual(success, True)
        self.assertEqual(len(targets), 2)
        self.assertDictEqual(targets[0], {
            "static_address": 0x50,
            "dynamic_address": 0x08,
            "bcr": 0x10,
            "dcr": 0xC3,
            "pid": ["0x65", "0x64", "0x00", "0x00", "0x00", "0x00"],
            
        })
        self.assertDictEqual(targets[1], {
            "static_address": 0x51,
            "dynamic_address": 0x09,
            "bcr": 0x03,
            "dcr": 0x63,
            "pid": ["0x5A", "0x00", "0x1D", "0x0F", "0x17", "0x02"],
        })

        self.device.close()

    def test_i3c_targets_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, targets) = i3c.targets()

        self.assertTupleEqual((success, targets), (True, []))

        self.device.close()

    def test_i3c_write_operation_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, _) = i3c.write(
            0x08,
            i3c.TransferMode.I3C_SDR,
            [0x00, 0x00],
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        self.assertEqual(success, False)

        self.device.close()

    def test_i3c_read_operation_when_bus_not_initialized(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        (success, _) = i3c.read(
            0x08,
            i3c.TransferMode.I3C_SDR,
            [0x00, 0x00],
            1
        )

        self.assertEqual(success, False)

        self.device.close()

    def test_i3c_successful_write_operation_on_target_should_return_none(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        subaddress = [0x00, 0x00]

        (success, result) = i3c.write(
            0x08,
            i3c.TransferMode.I3C_SDR,
            subaddress,
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        self.assertTupleEqual((success, result), (True, None))

        self.device.close()

    # Mock the controller's sync_submit method to simulate an exception.
    # It's important to note that this approach makes the test somewhat dependent
    # on the internal implementation of the device class.
    @patch.object(TransferController, "sync_submit", MagicMock(side_effect=Exception("This is a mock exception from the backend")))
    def test_backend_exception_is_wrapped(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        with self.assertRaises(BackendError):
            self.device.open()

    def test_i3c_successful_write_read_operations_on_target(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        subaddress = [0x00, 0x00]

        (success, result) = i3c.write(
            0x08,
            i3c.TransferMode.I3C_SDR,
            subaddress,
            [0xDE, 0xAD, 0xBE, 0xEF]
        )

        (success, result) = i3c.read(
            0x08,
            i3c.TransferMode.I3C_SDR,
            subaddress,
            4
        )

        self.assertTupleEqual((success, result), (True, [0xDE, 0xAD, 0xBE, 0xEF]))

        self.device.close()

    def test_ccc_getpid(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        (success, result) = i3c.ccc_getpid(0x08)

        self.assertTupleEqual((success, result), (True, [0x00, 0x00, 0x00, 0x00, 0x64, 0x65]))

        self.device.close()

    def test_spi_controller_set_bus_voltage(self):
        self.device.open()

        spi_controller = self.device.create_interface("spi.controller")

        (success, result) = spi_controller.set_bus_voltage(3300)

        self.assertTupleEqual((success, result), (True, 3300))
        self.assertEqual(spi_controller.bus_voltage, 3300)

        self.device.close()

    def test_spi_controller_init_bus(self):
        self.device.open()

        spi_controller = self.device.create_interface("spi.controller")

        (success, _) = spi_controller.init_bus()

        self.assertEqual(success, True)

        self.device.close()

    def test_spi_controller_set_parameters(self):
        self.device.open()

        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.init_bus()

        (success, _) = spi_controller.set_parameters(mode=SpiControllerMode.MODE_2)

        self.assertEqual(success, True)
        self.assertEqual(spi_controller.mode, SpiControllerMode.MODE_2)

        self.device.close()

    def test_spi_controller_get_parameters(self):
        self.device.open()

        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.init_bus()

        (_, response) = spi_controller.get_parameters()
        
        self.assertTupleEqual(response,(SpiControllerBitOrder.MSB, SpiControllerMode.MODE_0, SpiControllerDataWidth._8_BITS_DATA,
                                         SpiControllerChipSelect.CHIP_SELECT_0, SpiControllerChipSelectPolarity.ACTIVE_LOW, 10000000))

        (success, _) = spi_controller.set_parameters(bit_order=SpiControllerBitOrder.LSB, chip_select=SpiControllerChipSelect.CHIP_SELECT_2, chip_select_pol=SpiControllerChipSelectPolarity.ACTIVE_HIGH)

        self.assertEqual(success, True)

        (_, response) = spi_controller.get_parameters()
        
        self.assertTupleEqual(response,(SpiControllerBitOrder.LSB, SpiControllerMode.MODE_0, SpiControllerDataWidth._8_BITS_DATA,
                                         SpiControllerChipSelect.CHIP_SELECT_2, SpiControllerChipSelectPolarity.ACTIVE_HIGH, 10000000))

        self.device.close()

    # To run this test, it's necessary to connect the SPI Target device of Adafruit: FRAM memory MB85RS64V
    # Use the Supernova's breakout board and connect the VCC, GND, SCK, MISO, MOSI and CS signals of the memory
    # to its correspondent signal in the breakout board
    def test_spi_controller_transfer(self):
        self.device.open()

        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.set_bus_voltage(3300)
        spi_controller.init_bus()
        spi_controller.set_parameters(mode=SpiControllerMode.MODE_0)

        data = [0x9F]
        read_length = 4
        transfer_length = len(data) + read_length

        (success, result) = spi_controller.transfer(data, transfer_length)

        self.assertTupleEqual((success, result), (True, [0x00, 0x04, 0x7F, 0x03, 0x02]))
    def test_target_reset_read_reset_action(self):

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        (success, result) = i3c.target_reset(0x08,0x00, TransferDirection.READ)

        self.assertTupleEqual((success, result), (True, [0x00]))

        self.device.close()

    def test_target_reset_write_reset_action(self):

        self.device.open()

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        (success, result) = i3c.target_reset(0x08,I3cTargetResetDefByte.RESET_I3C_PERIPHERAL, TransferDirection.WRITE)
        print(success, result)

        self.assertTupleEqual((success, result), (True, None))

        self.device.close()

if __name__ == "__main__":
    unittest.main()
