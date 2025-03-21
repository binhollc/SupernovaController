import os
import unittest

from binhosimulators import BinhoSupernovaSimulator
from supernovacontroller.sequential.i2c import SupernovaI2CBlockingInterface
from supernovacontroller.sequential.supernova_device import SupernovaDevice

class TestI2CSupernovaController(unittest.TestCase):
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
        self.i2c : SupernovaI2CBlockingInterface = self.device.create_interface("i2c")

    def tearDown(self):
        self.device.close()
        

    def test_i2c_set_parameters(self):
        (success, result) = self.i2c.set_parameters(500000)

        self.assertEqual(success, True)
        self.assertEqual(result, (500000))

    def test_i2c_should_not_throw_error_if_bus_voltage_is_not_set(self):
        (success, _) = self.i2c.read_from(0x50, [0x00,0x00], 4)

        self.assertEqual(success, True)

    def test_i2c_set_bus_voltage_or_init_bus_are_equivalent(self):
        self.i2c.set_bus_voltage(3300)
        self.i2c.set_parameters(500000)

        try:
            self.i2c.read_from(0x50, [0x00,0x00], 1)
        except Exception as e:
            self.fail(f"self.i2c read raised an exception {e}")
            
    def test_i2c_set_pull_up_resistor(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        (success, message) = self.i2c.set_pull_up_resistors("DISABLE")
        self.assertTupleEqual((True, "DISABLE"), (success, message), f"Disabling Pullup failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(150)
        self.assertTupleEqual((True, 150), (success, message), f"Setting 150 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(220)
        self.assertTupleEqual((True, 220), (success, message), f"Setting 220 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(330)
        self.assertTupleEqual((True, 330), (success, message), f"Setting 330 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(470)
        self.assertTupleEqual((True, 470), (success, message), f"Setting 470 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(680)
        self.assertTupleEqual((True, 680), (success, message), f"Setting 680 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(1000)
        self.assertTupleEqual((True, 1000), (success, message), f"Setting 1000 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(1500)
        self.assertTupleEqual((True, 1500), (success, message), f"Setting 1500 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(2200)
        self.assertTupleEqual((True, 2200), (success, message), f"Setting 2200 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(3300)
        self.assertTupleEqual((True, 3300), (success, message), f"Setting 3300 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(4700)
        self.assertTupleEqual((True, 4700), (success, message), f"Setting 4700 Ohm failed: {message}")
        (success, message) = self.i2c.set_pull_up_resistors(10000)
        self.assertTupleEqual((True, 10000), (success, message), f"Setting 10000 Ohm failed: {message}")

    def test_i2c_set_pull_up_resistor_exception_unsupported_value(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        with self.assertRaises(ValueError):
            self.i2c.set_pull_up_resistors(0)
        with self.assertRaises(ValueError):
            self.i2c.set_pull_up_resistors(18993)
        with self.assertRaises(ValueError):
            self.i2c.set_pull_up_resistors(1501)

    def test_i2c_write(self):
        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)
        (success, result) = self.i2c.write(0x50, [0x00,0x00], [0xDE, 0xAD, 0xBE, 0xEF])

        self.assertEqual(success, True)
        self.assertEqual(result, None)

    def test_i2c_write_non_stop(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)
        
        data_length = 70
        data_to_write = [55 for i in range(0, data_length)]
        
        (success, result) = self.i2c.write_non_stop(0x50, [0x01,0x00], data_to_write)
        self.assertEqual(success, True)
        self.assertEqual(result, None)
        
        (success, result) = self.i2c.read_from(0x50, [0x01,0x00], data_length)
        self.assertTupleEqual((success, result), (True, data_to_write))

    def test_i2c_write_non_stop_should_nack(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)
        
        data_length = 70
        data_to_write = [55 for i in range(0, data_length)]
        
        (success, result) = self.i2c.write_non_stop(0x56, [0x01,0x00], data_to_write)
        self.assertTupleEqual((success, result), (False, "I2C_NACK_ADDRESS"))

    def test_i2c_write_read_from(self):
        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)

        self.i2c.write(0x50, [0x00,0x00], [0xDE, 0xAD, 0xBE, 0xEF])
        (success, data) = self.i2c.read_from(0x50, [0x00,0x00], 4)

        self.assertEqual(success, True)
        self.assertEqual(data, [0xDE, 0xAD, 0xBE, 0xEF])

    def test_i2c_write_continuous_read(self):
        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)

        self.i2c.write(0x50, [0x00, 0x00], [0x01, 0x02, 0x03, 0x04])
        self.i2c.write(0x50, [], [0x00, 0x00])
        (success, a) = self.i2c.read(0x50, 1)
        (success, b) = self.i2c.read(0x50, 1)
        (success, cd) = self.i2c.read(0x50, 2)

        self.assertEqual(success, True)
        self.assertEqual(a, [0x01])
        self.assertEqual(b, [0x02])
        self.assertEqual(cd, [0x03, 0x04])

    def test_i2c_write_NACK(self):
        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)
        (success, result) = self.i2c.write(0x99, [0x00,0x00], [0xDE, 0xAD, 0xBE, 0xEF])

        self.assertEqual(result, "I2C_NACK_ADDRESS")
        self.assertEqual(success, False)

    def test_i2c_write_read_from_NACK(self):
        self.i2c.init_bus(3300)
        self.i2c.set_parameters(500000)

        (success, data) = self.i2c.read_from(0x99, [0x00,0x00], 4)

        self.assertEqual(data, "I2C_NACK_ADDRESS")
        self.assertEqual(success, False)
        
if __name__ == "__main__":
    unittest.main()
