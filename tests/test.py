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
    SpiControllerChipSelect, SpiControllerChipSelectPolarity,
    GpioPinNumber, GpioLogicLevel, GpioFunctionality, GpioTriggerType)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binhosimulators import BinhoSupernovaSimulator

class TestDeviceSupernovaController(unittest.TestCase):
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

    def tearDown(self):
        self.device.close()

    def __validate_device_info(self, deviceInfo):
        self.assertRegex(deviceInfo["hw_version"], r"^[A-Za-z0-9]$", "Invalid hw_version format")
        self.assertRegex(deviceInfo["fw_version"], r"^\d+\.\d+\.\d+$", "Invalid fw_version format")
        self.assertRegex(deviceInfo["serial_number"], r"^[A-Fa-f0-9]+$", "Invalid serial_number format")
        self.assertEqual(deviceInfo["manufacturer"], "Binho LLC", "Invalid manufacturer string")
        self.assertEqual(deviceInfo["product_name"], "Binho Supernova", "Invalid product name")

    def test_open_device_with_wrong_address(self):
        d = SupernovaDevice()

        with self.assertRaises(DeviceOpenError):
            d.open("whatever")

    def test_open_device_and_close(self):
        self.__validate_device_info(self.device_info)

    def test_open_device_more_than_once(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        with self.assertRaises(DeviceAlreadyMountedError):
            self.device.open()

    def test_create_interface_before_open_throws_error(self):
        d = SupernovaDevice()
        with self.assertRaises(DeviceNotMountedError):
            d.create_interface("i3c.controller")

    def test_subsequent_calls_to_create_interface_retrieve_the_same_instance(self):
        instance_1 = self.device.create_interface("i3c.controller")
        instance_2 = self.device.create_interface("i3c.controller")

        self.assertEqual(instance_1, instance_2)

    def test_create_interface_wrong_name(self):
        with self.assertRaises(UnknownInterfaceError):
            self.device.create_interface("foo")

    # Mock the controller's sync_submit method to simulate an exception.
    # It's important to note that this approach makes the test somewhat dependent
    # on the internal implementation of the device class.
    @patch.object(TransferController, "sync_submit", MagicMock(side_effect=Exception("This is a mock exception from the backend")))
    def test_backend_exception_is_wrapped(self):
        if not self.use_simulator:
            self.skipTest("For simulator only")

        with self.assertRaises(BackendError):
            self.device.get_hardware_version()

    def test_spi_controller_set_bus_voltage(self):
        spi_controller = self.device.create_interface("spi.controller")

        (success, result) = spi_controller.set_bus_voltage(3300)

        self.assertTupleEqual((success, result), (True, 3300))
        self.assertEqual(spi_controller.bus_voltage, 3300)

    def test_spi_controller_init_bus(self):
        spi_controller = self.device.create_interface("spi.controller")

        (success, _) = spi_controller.init_bus()

        self.assertEqual(success, True)

    def test_spi_controller_set_parameters(self):
        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.init_bus()

        (success, _) = spi_controller.set_parameters(mode=SpiControllerMode.MODE_2)

        self.assertEqual(success, True)
        self.assertEqual(spi_controller.mode, SpiControllerMode.MODE_2)

    def test_spi_controller_get_parameters(self):
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

    # To run this test, it's necessary to connect the SPI Target device of Adafruit: FRAM memory MB85RS64V
    # Use the Supernova's breakout board and connect the VCC, GND, SCK, MISO, MOSI and CS signals of the memory
    # to its correspondent signal in the breakout board
    def test_spi_who_am_i_fram_MB85RS64V(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.set_bus_voltage(3300)
        spi_controller.init_bus()
        spi_controller.set_parameters(mode=SpiControllerMode.MODE_0)

        data = [0x9F]
        read_length = 4
        transfer_length = len(data) + read_length

        (success, result) = spi_controller.transfer(data, transfer_length)

        self.assertTupleEqual((success, result), (True, [0x00, 0x04, 0x7F, 0x03, 0x02]))

    def test_spi_sim_transfer(self):
        if not self.use_simulator:
            self.skipTest("For simulated device only")

        spi_controller = self.device.create_interface("spi.controller")

        spi_controller.set_bus_voltage(3300)
        spi_controller.init_bus()
        spi_controller.set_parameters(mode=SpiControllerMode.MODE_0)

        data = [0xAA, 0xBB, 0xCC]
        read_length = 2
        transfer_length = len(data) + read_length

        (success, result) = spi_controller.transfer(data, transfer_length)

        self.assertTupleEqual((success, result), (True, [0xAA, 0xBB, 0xCC, 0x00, 0x00]))
        
    def test_gpio_set_bus_voltage(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        gpio = self.device.create_interface("gpio")
        
        (success, result) = gpio.set_pins_voltage(3300)
        
        self.assertTupleEqual((success, result), (True, 3300))
        self.assertEqual(gpio.pins_voltage, 3300)

    def test_gpio_configure_pin(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        
        gpio = self.device.create_interface("gpio")
        
        (success, result) = gpio.configure_pin(GpioPinNumber.GPIO_6, GpioFunctionality.DIGITAL_OUTPUT)
        self.assertTupleEqual((success, result), (True, None))
        
        (success, result) = gpio.configure_pin(GpioPinNumber.GPIO_5, GpioFunctionality.DIGITAL_INPUT)
        self.assertTupleEqual((success, result), (True, None))

    def test_gpio_digital_write_read(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        
        gpio = self.device.create_interface("gpio")
        
        gpio.configure_pin(GpioPinNumber.GPIO_6, GpioFunctionality.DIGITAL_OUTPUT)
        gpio.configure_pin(GpioPinNumber.GPIO_5, GpioFunctionality.DIGITAL_INPUT)
        
        (success, _) = gpio.digital_write(GpioPinNumber.GPIO_6, GpioLogicLevel.HIGH)
        self.assertEqual(success, True)
        
        (success, value) = gpio.digital_read(GpioPinNumber.GPIO_5)
        self.assertEqual(success, True)
        self.assertEqual(value, GpioLogicLevel.HIGH.name)
        
        (success, _) = gpio.digital_write(GpioPinNumber.GPIO_6, GpioLogicLevel.LOW)
        self.assertEqual(success, True)
        
        (success, value) = gpio.digital_read(GpioPinNumber.GPIO_5)
        self.assertEqual(success, True)
        self.assertEqual(value, GpioLogicLevel.LOW.name)

    def test_gpio_set_disable_interrupt(self):
        if self.use_simulator:
            self.skipTest("For real device only")
        
        gpio = self.device.create_interface("gpio")
        
        gpio.configure_pin(GpioPinNumber.GPIO_5, GpioFunctionality.DIGITAL_INPUT)
        
        (success, result) = gpio.set_interrupt(GpioPinNumber.GPIO_5, GpioTriggerType.TRIGGER_BOTH_EDGES)
        self.assertTupleEqual((success, result), (True, None))
        
        (success, result) = gpio.disable_interrupt(GpioPinNumber.GPIO_5)
        self.assertTupleEqual((success, result), (True, None))

    def test_trigger_target_reset_pattern(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        i3c = self.device.create_interface("i3c.controller")

        i3c.init_bus(3300)

        (success, result) = i3c.trigger_target_reset_pattern()

        self.assertTupleEqual((success, result), (True, None))

if __name__ == "__main__":
    unittest.main()
