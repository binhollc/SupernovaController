import os  
import sys  
import threading  
import unittest  

from supernovacontroller.sequential import SupernovaDevice  
from supernovacontroller.sequential.uart import SupernovaUARTBlockingInterface  
from BinhoSupernova.commands.definitions import (  
    UartControllerBaudRate as baud,  
    UartControllerParity as parity,  
    UartControllerDataSize as dataSize,  
    UartControllerStopBit as stopBit  
)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from binhosimulators import BinhoSupernovaSimulator

# TODO @BMC2-1512 Update the simulator to support the execution/usage via SNController 
class TestSupernovaControllerUART(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Initializes the testing class. Determines whether to use the simulator or real device
        based on the "USE_REAL_DEVICE" environment variable. Default is to use the simulator.
        """
        # NOTE: These tests only work for the real device until BMC2-1512 is solved
        cls.use_simulator = not os.getenv("USE_REAL_DEVICE", "False") == "True"

    def setUp(self):
        self.device = SupernovaDevice()
        if self.use_simulator:
            self.device.driver = BinhoSupernovaSimulator()

    def tearDown(self):
        self.device.close()

    def test_uart_echo_message_real_device(self):
        if self.use_simulator:
            self.skipTest("For real device only")

        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        (success, _) = uart.set_bus_voltage(3300)
        uart.init_bus()

        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        (success, _) = uart.send(data)
        (successReceive, response) = uart.wait_for_notification(1)

        self.assertEqual(success, True)
        self.assertTupleEqual((successReceive, response), (True, data), f"Failed echo: {response}")

    def test_set_bus_voltage(self):
        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        (success, _) = uart.set_bus_voltage(3300)

        self.assertEqual(success, True)

    def test_wait_timeout(self):
        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        uart.set_bus_voltage(3300)
        uart.init_bus()

        timer = threading.Timer(5, lambda: self.fail("Timeout was exceeded"))  
        timer.start() 

        try:  
            success, response = uart.wait_for_notification(4)  
            self.assertTupleEqual(  
                (False, "Timeout occurred while waiting for the UART receive notification"),  
                (success, response),  
                f"Failed non-timeout response: {response}"  
            )  
        finally:  
            timer.cancel()

    # TODO Fails due to lack of management of ALREADY_INITIALIZED in the blocking interface
    def test_uart_init_bus(self):
        if self.use_simulator:
            self.skipTest("For real device only")
            # Currently there is a discrepancy in signature for the init bus methods between simulator and real SDK, making this test fail with the SIM

        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        uart.set_bus_voltage(3300)
        (success, response) = uart.init_bus()

        self.assertEqual(success, True, f"Failed: {response}")

    # TODO Fails due to lack of management of ALREADY_INITIALIZED in the blocking interface
    def test_uart_multiple_init_bus(self):
        if self.use_simulator:
            self.skipTest("For real device only")
            # Currently there is a discrepancy in signature for the init bus methods between simulator and real SDK, making this test fail with the SIM

        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        uart.set_bus_voltage(3300)

        (success, response) = uart.init_bus()
        self.assertEqual(True, success, f"Failed on first init: {response}")

        (success, response) = uart.init_bus()
        self.assertTupleEqual((False, "UART_ALREADY_INITIALIZED_ERROR"), (success, response), f"Failed on second init: {response}") # Revise this once the error is better handled, it is not necessarily the way forward presenting the error

    def test_uart_set_get_params(self):
        if self.use_simulator:
            self.skipTest("For real device only")
            # Currently there is a discrepancy in signature for the init bus methods between simulator and real SDK, making this test fail with the SIM

        self.device.open()
        uart : SupernovaUARTBlockingInterface = self.device.create_interface("uart") # Type hinting for easier development

        uart.set_bus_voltage(3300)
        (success, _) = uart.init_bus()

        (success, _) = uart.get_parameters()
        self.assertEqual(success, True)

        params = (baud.UART_BAUD_2400, dataSize.UART_8BIT_BYTE, True, parity.UART_ODD_PARITY, stopBit.UART_TWO_STOP_BIT)
        param_names = ["UART_BAUD_2400", "UART_ODD_PARITY", "UART_8BIT_BYTE", "UART_TWO_STOP_BIT", True]
        (success, _) = uart.set_parameters(baudrate=params[0], data_size=params[1], hardware_handshake=params[2], parity=params[3], stop_bit=params[4])
        self.assertEqual(success, True)

        (success, response) = uart.get_parameters()

        # pass the enum member to strs of their names, (except the bool)
        parsed_response = [response[index].name if not isinstance(response[index], bool) else response[index] for index in range(len(response))]

        self.assertTupleEqual((True, param_names), (success, parsed_response))

if __name__ == "__main__":
    unittest.main()