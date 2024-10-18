
from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.commands.definitions import (
    UartControllerBaudRate, UartControllerParity, UartControllerDataSize,
    UartControllerStopBit, COMMANDS_DICTIONARY,
    UART_CONTROLLER_INIT, UART_CONTROLLER_SET_PARAMETERS, UART_CONTROLLER_SEND
)
from supernovacontroller.errors import BackendError
from threading import Event

class UARTNotificationHandler:

    def __init__(self, notification_subscription):
        """
        Initializes the UARTNotificationHandler.

        Args:
        notification_subscription: A subscription object for receiving notifications.

        Note:
        The notification_subscription parameter is used to set up the subscription
        for handling UART data reception notifications within the handler.
        """

        self.last_notification = Event()
        self.last_notification_message = None
        notification_subscription(name="UART Receive Notification", filter_func=self.__is_uart_receive, handler_func=self.__handle_uart_receive)

    def wait_for_notification(self, time_out):
        """
        Waits for a UART data reception notification.

        This method waits for a UART data reception notification for a specified duration.

        Args:
        time_out: The duration in seconds to wait for the notification.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of receiving the notification.
            - The second element is either the received message if successful or None if no notification is received.
        """

        data_has_been_received = self.last_notification.wait(time_out)
        self.last_notification.clear()

        if not data_has_been_received:
            self.last_notification_message = None

        return data_has_been_received, self.last_notification_message
    
    def __is_uart_receive(self, name, message):
        """
        Checks if the received notification is related to UART reception.

        Args:
        name: The name of the received notification.
        message: The content of the received notification.

        Returns:
        bool: True if the notification is related to UART reception, False otherwise.
        """
 
        # Hot-Fix to solve extra space in the firmware release
        return message['name'].strip() == "UART CONTROLLER RECEIVE MESSAGE"
    
    def __handle_uart_receive(self, name, message):
        """
        This method handles the UART received notification by setting the last received message and
        triggering the last notification event.

        Args:
        name: The name of the received notification.
        message: The content of the received notification.
        """

        self.last_notification_message = message
        self.last_notification.set()
        
class SupernovaUARTBlockingInterface:
    # Private Methods
    def __init__(self, driver: Supernova, controller: TransferController, notification_subscription):
        """
        Initializes a new instance of the SupernovaUARTBlockingInterface class. This interface is used for blocking UART communication with the Supernova.
        By default the UART peripheral is configured with the following parameters:
            Baudrate: 9600
            Parity: No Parity
            Data size: 8 bit data
            Stop bit for framing: 1 stop bit
            Hardware handshake (RTS/CTS): disabled, can't be changed
        """

        # Supernova driver instance
        self.driver = driver
        # Transfer controller instance
        self.controller = controller
        # UART communication parameters
        self.baudrate = UartControllerBaudRate.UART_BAUD_9600
        self.parity = UartControllerParity.UART_NO_PARITY
        self.data_size = UartControllerDataSize.UART_8BIT_BYTE
        self.stop_bit = UartControllerStopBit.UART_ONE_STOP_BIT
        self.hardware_handshake = False
        self.bus_voltage = None
        # UART receive notification handler
        self.uart_notification = UARTNotificationHandler(notification_subscription)

    def __store_parameters(self, baudrate: UartControllerBaudRate=None, hardware_handshake: bool=None , parity: UartControllerParity=None, data_size: UartControllerDataSize=None, stop_bit: UartControllerStopBit=None):
        """
        Stores the UART communication parameters.

        This method allows setting and updating specific UART communication parameters such as baudrate, hardware handshake,
        parity, data size, and stop bit. It selectively updates the parameters if new values are provided, retaining existing values otherwise.

        Args:
        baudrate (UartControllerBaudRate, optional): The baudrate for UART communication (default: None).
        hardware_handshake (bool, optional): The hardware handshake setting for UART communication (default: None).
        parity (UartControllerParity, optional): The parity setting for UART communication (default: None).
        data_size (UartControllerDataSize, optional): The data size for UART communication (default: None).
        stop_bit (UartControllerStopBit, optional): The stop bit setting for UART communication (default: None).
        """

        # Update parameters if provided
        self.baudrate = baudrate or self.baudrate
        self.hardware_handshake = hardware_handshake or self.hardware_handshake
        self.parity = parity or self.parity
        self.data_size = data_size or self.data_size
        self.stop_bit = stop_bit or self.stop_bit

    def __check_data_complete(self):
        """
        Checks if all required UART communication parameters are complete.

        This method verifies whether all the essential UART communication parameters, including baudrate,
        hardware handshake, parity, data size, and stop bit, have been properly set and are not None.

        Returns:
        bool: True if all parameters are complete, False otherwise.
        """

        # Check if all the configuration for UART communication are set
        return all([
            self.baudrate is not None,
            self.hardware_handshake is not None,
            self.parity is not None,
            self.data_size is not None,
            self.stop_bit is not None
        ])

    def __check_if_response_is_correct(self, response):
        """
        Checks if the response received from the Supernova indicates successful execution of the UART method.

        Args:
        response (dict): A dictionary containing response data from the Supernova UART request.

        Returns:
        bool: True if the response indicates successful, False otherwise.
        """

        # Check if the USB, manager or driver had issues handling the UART request
        return len(self.__get_response_errors(response)) == 0
    
    def __get_response_errors(self, response: dict):
        """
        Checks if the response received any errors from the Supernova and returns them (if any).

        Args:
        response (dict): A dictionary containing response data from the Supernova UART request.

        Returns:
        [ String ]: List of errors, in order usb_error, manager_error and driver_error.
        """

        result = []
        if response["usb_error"] != "CMD_SUCCESSFUL": result.append(response["usb_error"])
        if response["manager_error"] != "UART_NO_ERROR": result.append(response["manager_error"])
        if response["driver_error"] != "NO_TRANSFER_ERROR": result.append(response["driver_error"])
        return result
    
    def set_bus_voltage(self, voltage_mv: int):
        """
        Sets the bus voltage for the UART interface to a specified value.
        The method updates the bus voltage of the instance only if the operation is successful. The success
        or failure of the operation is determined based on the response from the hardware.

        Args:
        voltage_mv (int): The voltage value to be set for the UART bus in millivolts (mV).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False)
              of the operation.
            - The second element is either the new bus voltage (indicating success) or an
              error message detailing the failure, obtained from the device's response.

        Note:
        - The method does not perform validation on the input voltage value. Users of this
          method should ensure that the provided voltage value is within acceptable limits
          for their specific hardware configuration.
        - The bus voltage is updated in the interface instance only if the operation is successful.

        Raises:
        BackendError: If an exception occurs setting the bus voltage process.
        """

        # Set the UART bus voltage accordingly
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.setI2cSpiUartBusVoltage(transfer_id, voltage_mv),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        # Check if the response is of the expected type (by name) and it was successful 
        response_success = responses[0]["name"] == "SET I2C-SPI-UART BUS VOLTAGE" and responses[0]["result"] == "SYS_NO_ERROR"

        # If successful, update the bus voltage
        if response_success:
            result = (True, voltage_mv)
            self.bus_voltage = voltage_mv
        # If not successful update method response
        else:
            result = (False, responses[0]["result"])
            self.bus_voltage = None

        return result
    
    def init_bus(self, baudrate: UartControllerBaudRate=None, hardware_handshake: bool=None , parity: UartControllerParity=None, data_size: UartControllerDataSize=None, stop_bit: UartControllerStopBit=None):
        """
        Initializes the UART bus with specified parameters.

        This method initializes the UART bus with the provided communication parameters such as baudrate,
        hardware handshake, parity, data size, and stop bit. If parameters are provided, it configures the bus
        accordingly; otherwise, it retains the current settings.

        Args:
        baudrate (UartControllerBaudRate, optional): The baudrate for UART communication (default: None).
        hardware_handshake (bool, optional): The hardware handshake setting for UART communication (default: None).
        parity (UartControllerParity, optional): The parity setting for UART communication (default: None).
        data_size (UartControllerDataSize, optional): The data size for UART communication (default: None).
        stop_bit (UartControllerStopBit, optional): The stop bit setting for UART communication (default: None).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the initialization.
            - The second element is a string describing the result of the initialization process.

        Raises:
        BackendError: If an exception occurs during the initialization process.

        Note:
        - The method does not perform validation on any of the UART communication parameters. Users of this
          method should ensure that the provided configuration is valid.
        """

        # Update the UART class attributes with the provided data
        self.__store_parameters(baudrate = baudrate, hardware_handshake = hardware_handshake, parity = parity, data_size = data_size, stop_bit = stop_bit)
        # Check if all the needed configurations for UART communication are correctly set
        is_data_complete = self.__check_data_complete()
        # Return failure if data is incomplete
        if not is_data_complete: 
            return (False, "Init failed, incomplete parameters to initialize bus")
        
        # Request UART bus initialization 
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.uartControllerInit(id = transfer_id, baudrate = self.baudrate, hardwareHandshake = self.hardware_handshake, parityMode = self.parity, dataSize = self.data_size, stopBit = self.stop_bit)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        # Check if the response is of the expected type (by name) and it was successful 
        response_success = responses[0]["name"].strip() == COMMANDS_DICTIONARY[UART_CONTROLLER_INIT]["name"].strip() and self.__check_if_response_is_correct(responses[0])

        return (response_success, "Success" if response_success else self.__get_response_errors(responses[0]))

    def set_parameters(self, baudrate: UartControllerBaudRate=None, hardware_handshake: bool=None , parity: UartControllerParity=None, data_size: UartControllerDataSize=None, stop_bit: UartControllerStopBit=None):
        """
        Sets UART communication parameters.

        This method sets the UART communication parameters such as baudrate, hardware handshake,
        parity, data size, and stop bit. If parameters are provided, it configures the parameters;
        otherwise, it retains the current settings.

        Args:
        baudrate (UartControllerBaudRate, optional): The baudrate for UART communication (default: None).
        hardware_handshake (bool, optional): The hardware handshake setting for UART communication (default: None).
        parity (UartControllerParity, optional): The parity setting for UART communication (default: None).
        data_size (UartControllerDataSize, optional): The data size for UART communication (default: None).
        stop_bit (UartControllerStopBit, optional): The stop bit setting for UART communication (default: None).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of setting the parameters.
            - The second element is a string describing the result of setting the parameters.

        Raises:
        BackendError: If an exception occurs while setting the parameters.

        Note:
        - The method does not perform validation on any of the UART communication parameters. Users of this
          method should ensure that the provided configuration is valid.
        """

        # Update the UART class attributes with the provided data
        self.__store_parameters(baudrate = baudrate, hardware_handshake = hardware_handshake, parity = parity, data_size = data_size, stop_bit = stop_bit)
        # Check if all the needed configurations for UART communication are correctly set
        is_data_complete = self.__check_data_complete()
        # Return failure if data is incomplete
        if not is_data_complete: 
            return (False, "Set parameters failed, incomplete parameters to do set parameters")

        responses = None
        # Request UART set parameters 
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.uartControllerSetParameters(id = transfer_id, baudrate = self.baudrate, hardwareHandshake = self.hardware_handshake, parityMode = self.parity, dataSize = self.data_size, stopBit = self.stop_bit)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # Check if the response is of the expected type (by name) and it was successful 
        response_success = responses[0]["name"].strip() == COMMANDS_DICTIONARY[UART_CONTROLLER_SET_PARAMETERS]["name"].strip() and self.__check_if_response_is_correct(responses[0])

        return (response_success, "Success" if response_success else self.__get_response_errors(responses[0]))

    def get_parameters(self):
        """
        Retrieves the current UART communication parameters.

        This method retrieves the current UART communication parameters, including baudrate,
        parity, data size, stop bit, and hardware handshake.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) of retrieving parameters.
            - The second element is a tuple containing the current UART communication parameters:
                (baudrate, parity, data_size, stop_bit, hardware_handshake).
        """

        # return configured UART parameters
        return (True, (self.baudrate, self.parity, self.data_size, self.stop_bit, self.hardware_handshake))
    
    def send(self, data):
        """
        Sends data over the UART bus.

        This method sends the provided data over the UART bus if the bus is initialized. 

        Args:
        data: The data to be transmitted over the UART bus.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the send operation.
            - The second element is None.

        Raises:
        BackendError: If an exception occurs during the transmission process.
        """

        responses = None
        # Request UART send transaction
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.uartControllerSendMessage(id = transfer_id, data = data),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        # Check if the response is of the expected type (by name) and it was successful 
        response_success =  responses[0]["name"].strip() == COMMANDS_DICTIONARY[UART_CONTROLLER_SEND]["name"].strip() and self.__check_if_response_is_correct(responses[0])
            
        return (response_success, "Success" if response_success else self.__get_response_errors(responses[0]))
    
    def wait_for_notification(self, timeout):
        """
        Waits for UART receive notification.

        This method waits for a notification related to UART data reception for the specified timeout duration.
        It uses the UART notification subscription to wait for incoming data notifications.

        Args:
        timeout: The duration in seconds to wait for the notification.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of receiving the notification.
            - The second element is either the received payload if successful or an error message.
        """

        # Wait for a UART receive notification with the specified timeout
        received_data_flag, notification =  self.uart_notification.wait_for_notification(timeout)

        # Check if the notification was received within the timeout
        if received_data_flag is False:
            return (received_data_flag, "Timeout occurred while waiting for the UART receive notification")
        
        # Check if the reception of the UART message was successful
        response_ok = self.__check_if_response_is_correct(notification)
        # If there's an error in the received notification, return an error message
        if response_ok is False:
            return (response_ok, self.__get_response_errors(notification))
        
        # Return the received payload if the notification is correct
        return (response_ok, notification["payload"])    