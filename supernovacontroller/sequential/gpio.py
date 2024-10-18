from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.commands.definitions import (
    GpioPinNumber, GpioLogicLevel, GpioFunctionality, GpioTriggerType,
)
from supernovacontroller.errors import BackendError

class SupernovaGPIOInterface:
    def __init__(self, driver: Supernova, controller: TransferController, notification_subscription, hardware_version):
        """
        Initializes a new instance of the SupernovaGPIOInterface class. This interface is used for GPIO communication with the Supernova.
        """
        self.driver = driver
        self.controller = controller
        self.configured_pins = {}
        self.pins_voltage = None
        self.hardware_version = hardware_version

    def set_pins_voltage(self, voltage_mv: int):
        """
        Sets the bus voltage for the GPIO interface to a specified value.

        Args:
        voltage_mv (int): The voltage value to be set for the GPIO bus in millivolts (mV).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False)
              of the operation.
            - The second element is either the new bus voltage (indicating success) or an
              error message detailing the failure, obtained from the device's response.

        Note:
        - The SDK method called depends upon which hardware revision is connected.
          - If Rev. B is used, voltage can be set in pins 1 and 2 with setI3cBusVoltage(). Pins 3 to 6 are fixed at 3.3 V.
          - If Rev. C is used, voltage is set with setI2cSpiUartBusVoltage() for all pins.
        """
        set_voltage_method = None

        if self.hardware_version.startswith("HW-B"):
            set_voltage_method = self.driver.setI3cBusVoltage
            expected_command_name = "SET I3C BUS VOLTAGE"
        elif self.hardware_version.startswith("HW-C"):
            set_voltage_method = self.driver.setI2cSpiUartBusVoltage
            expected_command_name = "SET I2C-SPI-UART BUS VOLTAGE"
        else:
            raise BackendError(f"Unsupported hardware version: {self.hardware_version}")

        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: set_voltage_method(transfer_id, voltage_mv),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == expected_command_name and responses[0]["result"] == "SYS_NO_ERROR"

        if not response_success:
            return (False, responses[0]["result"])

        self.pins_voltage = voltage_mv

        return (True, voltage_mv)

    def __check_if_response_is_successful(self, response):
        """
        Checks if the response received from the Supernova indicates successful execution of the GPIO method.

        Args:
        response (dict): A dictionary containing response data from the Supernova GPIO request.

        Returns:
        bool: True if the response indicates successful, False otherwise.
        """
        return all([
            response["usb_error"] == "CMD_SUCCESSFUL",
            response["manager_error"] == "GPIO_NO_ERROR",
            response["driver_error"] == "GPIO_DRIVER_NO_ERROR"
        ])

    def configure_pin(self, pin_number: GpioPinNumber, functionality: GpioFunctionality):
        """
        Configures a GPIO pin with the specified functionality.

        Args:
        pin_number (GpioPinNumber): The GPIO pin number to configure.
        Possible values:
        - GPIO_1 to GPIO_6: Represents GPIO pins 1 to 6.

        functionality (GpioFunctionality): The desired functionality for the GPIO pin.
        Possible values:
        - DIGITAL_INPUT: Configures the pin as a digital input.
        - DIGITAL_OUTPUT: Configures the pin as a digital output.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the configuration.
            - The second element is a string describing the result of the configuration process.
        """
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.gpioConfigurePin(transfer_id, pin_number, functionality)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == "CONFIGURE GPIO PIN" and self.__check_if_response_is_successful(responses[0])

        if not response_success:
            return (False, "Configuration failed, error from the Supernova")

        self.configured_pins[pin_number] = functionality

        return (True, None)

    def digital_write(self, pin_number: GpioPinNumber, logic_level: GpioLogicLevel):
        """
        Writes a digital logic level to a GPIO pin.

        Args:
        pin_number (GpioPinNumber): The GPIO pin number to write to.
        logic_level (GpioLogicLevel): The logic level to write to the GPIO pin.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the write operation.
            - The second element is a string describing the result of the write operation.
        """
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.gpioDigitalWrite(transfer_id, pin_number, logic_level)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == "GPIO DIGITAL WRITE" and self.__check_if_response_is_successful(responses[0])

        if not response_success:
            return (False, "Digital write failed, error from the Supernova")

        return (True, None)

    def digital_read(self, pin_number: GpioPinNumber):
        """
        Reads the digital logic level from a GPIO pin.

        Args:
        pin_number (GpioPinNumber): The GPIO pin number to read from.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the read operation.
            - The second element is the logic level read from the GPIO pin if successful, or an error message if failed.
        """
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.gpioDigitalRead(transfer_id, pin_number)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == "GPIO DIGITAL READ" and self.__check_if_response_is_successful(responses[0])

        if not response_success:
            return (False, "Digital read failed, error from the Supernova")

        return (True, responses[0]["logic_level"])

    def set_interrupt(self, pin_number: GpioPinNumber, trigger: GpioTriggerType):
        """
        Sets an interrupt on a GPIO pin.

        Args:
        pin_number (GpioPinNumber): The GPIO pin number to set the interrupt on.
        trigger (GpioTriggerType): The trigger type for the interrupt.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of setting the interrupt.
            - The second element is a string describing the result of setting the interrupt.

        Note:
        -  In hardware revision B, all pins support GPIO interruption except for pin 3.
        """
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.gpioSetInterrupt(transfer_id, pin_number, trigger)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == "GPIO SET INTERRUPT" and self.__check_if_response_is_successful(responses[0])

        if not response_success:
            return (False, "Set interrupt failed, error from the Supernova")

        return (True, None)

    def disable_interrupt(self, pin_number: GpioPinNumber):
        """
        Disables an interrupt on a GPIO pin.

        Args:
        pin_number (GpioPinNumber): The GPIO pin number to disable the interrupt on.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of disabling the interrupt.
            - The second element is a string describing the result of disabling the interrupt.
        """
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.gpioDisableInterrupt(transfer_id, pin_number)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_success = responses[0]["name"] == "GPIO DISABLE INTERRUPT" and self.__check_if_response_is_successful(responses[0])

        if not response_success:
            return (False, "Disable interrupt failed, error from the Supernova")

        return (True, None)
