from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from supernovacontroller.errors import BackendError, BusVoltageError
from BinhoSupernova.commands.definitions import (
    SpiControllerBitOrder, SpiControllerMode, SpiControllerDataWidth,
    SpiControllerChipSelect, SpiControllerChipSelectPolarity, COMMANDS_DICTIONARY,
    SPI_CONTROLLER_INIT, SPI_CONTROLLER_SET_PARAMETERS, SPI_CONTROLLER_TRANSFER
)

class SupernovaSPIControllerBlockingInterface:
    # Private Methods
    def __init__(self, driver: Supernova, controller: TransferController, notification_subscription):
        """
        Initializes a new instance of the SupernovaSPIControllerBlockingInterface class. This interface is used for
        blocking SPI controller communication with the Supernova.
        By default the SPI controller peripheral is configured with the following parameters:
            Bit order: MSB first
            Mode: Mode 0
            Data width: 8 bits data width, can't be changed
            Chip select: CS0
            Chip select polarity: Active low
            Frequency: 10 MHz
        """

        # Supernova driver instance
        self.driver = driver
        # Transfer controller instance
        self.controller = controller
        # SPI controller communication parameters
        self.bit_order = SpiControllerBitOrder.MSB                        # MSB first
        self.mode = SpiControllerMode.MODE_0                             # Mode 0
        self.data_width = SpiControllerDataWidth._8_BITS_DATA             # 8 bits data width
        self.chip_select = SpiControllerChipSelect.CHIP_SELECT_0          # Chip select 0
        self.chip_select_pol = SpiControllerChipSelectPolarity.ACTIVE_LOW  # Active low
        self.frequency = 10000000                                        # 10 MHz
        self.bus_voltage = None
    
    def __store_parameters(self, bit_order: SpiControllerBitOrder=None, mode: SpiControllerMode=None, chip_select: SpiControllerChipSelect=None,
                           chip_select_pol: SpiControllerChipSelectPolarity=None, frequency: int=None):
        """
        Stores the SPI controller communication parameters.

        This method allows setting and updating specific SPI controller communication parameters such as bit order, spi mode,
        data width, chip select, chip select polarity and frequency. It selectively updates the parameters if new values are provided,
        retaining existing values otherwise.

        Args:
        bit_order (SpiControllerBitOrder, optional): The bit order for SPI communication (default: None).
        mode (SpiControllerMode, optional): The mode for SPI communication (default: None).
        chip_select (SpiControllerChipSelect, optional): The selected Chip to communicate with (default: None).
        chip_select_pol (SpiControllerChipSelectPolarity, optional): The chip select polarity setting for SPI communication (default: None).
        frequency (int, optional): The clock frequency for the SPI communication (default: None).
        """

        # Update parameters if provided
        self.bit_order = bit_order or self.bit_order
        self.mode = mode or self.mode
        self.chip_select = chip_select or self.chip_select
        self.chip_select_pol = chip_select_pol or self.chip_select_pol
        self.frequency = frequency or self.frequency

    def __check_data_complete(self):
        """
        Checks if all required SPI controller communication parameters are complete.

        This method verifies whether all the essential SPI controller communication parameters, including bit order, spi mode,
        data width, chip select, chip select polarity and frequency, have been properly set and are not None.

        Returns:
        bool: True if all parameters are complete, False otherwise.
        """

        # Check if all the configuration for SPI controller communication are set
        return all([
            self.bit_order is not None,
            self.mode is not None,
            self.data_width is not None,
            self.chip_select is not None,
            self.chip_select_pol is not None,
            self.frequency is not None
        ])
    
    def __check_if_response_is_correct(self, response):
        """
        Checks if the response received from the Supernova indicates successful execution of the SPI controller method.

        Args:
        response (dict): A dictionary containing response data from the Supernova SPI controller request.

        Returns:
        bool: True if the response indicates successful, False otherwise.
        """

        # Check if the USB, manager or driver had issues handling the SPI controller request
        return all([
            response["usb_error"] == "CMD_SUCCESSFUL",
            response["manager_error"] == "SPI_NO_ERROR" or response["manager_error"] == "SPI_ALREADY_INITIALIZED_ERROR",
            response["driver_error"] == "SPI_DRIVER_NO_TRANSFER_ERROR"
        ])
    
    def set_bus_voltage(self, voltage_mv: int):
        """
        Sets the bus voltage for the SPI controller interface to a specified value.
        The method updates the bus voltage of the instance only if the operation is successful. The success
        or failure of the operation is determined based on the response from the hardware.

        Args:
        voltage_mv (int): The voltage value to be set for the SPI bus in millivolts (mV).

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

        # Set the SPI bus voltage accordingly
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
    
    def init_bus(self, bit_order: SpiControllerBitOrder=None, mode: SpiControllerMode=None,
                 chip_select: SpiControllerChipSelect=None, chip_select_pol: SpiControllerChipSelectPolarity=None, frequency: int=None):
        """
        Initializes the SPI bus with specified parameters.

        This method initializes the SPI bus with the provided communication parameters such as bit order, spi mode,
        chip select, chip select polarity and frequency. If parameters are provided, it configures the bus
        accordingly; otherwise, it retains the current settings.

        Args:
        bit_order (SpiControllerBitOrder, optional): The bit order for SPI communication (default: None).
        mode (SpiControllerMode, optional): The mode for SPI communication (default: None).
        chip_select (SpiControllerChipSelect, optional): The selected Chip to communicate with (default: None).
        chip_select_pol (SpiControllerChipSelectPolarity, optional): The chip select polarity setting for SPI communication (default: None).
        frequency (int, optional): The clock frequency for the SPI communication (default: None).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the initialization.
            - The second element is a string describing the result of the initialization process.

        Raises:
        BackendError: If an exception occurs during the initialization process.

        Note:
        - The method does not perform validation on any of the SPI communication parameters. Users of this
          method should ensure that the provided configuration is valid.
        """

        # Update the SPI class attributes with the provided data
        self.__store_parameters(bit_order=bit_order, mode=mode, chip_select=chip_select, chip_select_pol=chip_select_pol, frequency=frequency)
        # Check if all the needed configurations for SPI communication are correctly set
        is_data_complete = self.__check_data_complete()
        # Return failure if data is incomplete
        if not is_data_complete: 
            return (False, "Init failed, incomplete parameters to initialize bus")
        
        # Request SPI controller initialization 
        responses = None
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.spiControllerInit(id=transfer_id, bitOrder=self.bit_order, mode=self.mode, dataWidth=self.data_width, chipSelect=self.chip_select, chipSelectPol=self.chip_select_pol, frequency=self.frequency)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        # Check if the response is of the expected type (by name) and it was successful 
        response_success = responses[0]["name"] == COMMANDS_DICTIONARY[SPI_CONTROLLER_INIT]["name"] and self.__check_if_response_is_correct(responses[0])

        return (response_success, "Success" if response_success else "Init failed, error from the Supernova")
     
    def set_parameters(self, bit_order: SpiControllerBitOrder=None, mode: SpiControllerMode=None,
                       chip_select: SpiControllerChipSelect=None, chip_select_pol: SpiControllerChipSelectPolarity=None, frequency: int=None):
        """
        Sets SPI controller communication parameters.

        This method sets the SPI controller communication parameters such as bit order, spi mode, chip select,
        chip select polarity and frequency. If parameters are provided, it configures the parameters;
        otherwise, it retains the current settings.

        Args:
        bit_order (SpiControllerBitOrder, optional): The bit order for SPI communication (default: None).
        mode (SpiControllerMode, optional): The mode for SPI communication (default: None).
        chip_select (SpiControllerChipSelect, optional): The selected Chip to communicate with (default: None).
        chip_select_pol (SpiControllerChipSelectPolarity, optional): The chip select polarity setting for SPI communication (default: None).
        frequency (int, optional): The clock frequency for the SPI communication (default: None).

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of setting the parameters.
            - The second element is a string describing the result of setting the parameters.

        Raises:
        BackendError: If an exception occurs while setting the parameters.

        Note:
        - The method does not perform validation on any of the SPI communication parameters. Users of this
          method should ensure that the provided configuration is valid.
        """

        # Update the SPI class attributes with the provided data
        self.__store_parameters(bit_order=bit_order, mode=mode, chip_select=chip_select, chip_select_pol=chip_select_pol, frequency=frequency)
        # Check if all the needed configurations for SPI communication are correctly set
        is_data_complete = self.__check_data_complete()
        # Return failure if data is incomplete
        if not is_data_complete: 
            return (False, "Set parameters failed, incomplete parameters to do set parameters")

        responses = None
        # Request SPI controller set parameters 
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.spiControllerSetParameters(id=transfer_id, bitOrder=self.bit_order, mode=self.mode, dataWidth=self.data_width, chipSelect=self.chip_select, chipSelectPol=self.chip_select_pol, frequency=self.frequency)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # Check if the response is of the expected type (by name) and it was successful 
        response_success = responses[0]["name"] == COMMANDS_DICTIONARY[SPI_CONTROLLER_SET_PARAMETERS]["name"] and self.__check_if_response_is_correct(responses[0])

        return (response_success, "Success" if response_success else "Set Parameters failed, error from the Supernova")

    def get_parameters(self):
        """
        Retrieves the current SPI controller communication parameters.

        This method retrieves the current SPI controller communication parameters, including bit order, spi mode,
        data width, chip select, chip select polarity and frequency.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) of retrieving parameters.
            - The second element is a tuple containing the current SPI controller communication parameters:
                (bit_order, mode, data_width, chip_select, chip_select_pol, frequency).
        """

        # return configured SPI controller parameters
        return (True, (self.bit_order, self.mode, self.data_width, self.chip_select, self.chip_select_pol, self.frequency))
    
    def transfer(self, data, transfer_length):
        """
        Transfers data over the SPI bus.

        This method performs a transfer of the provided data over the SPI bus if the bus is initialized. 

        Args:
        data: The data to be transmitted over the SPI bus.
        transfer_length: 2-bytes integer that represents the transfer length. The range allowed is [1, 1024].

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the send operation.
            - The second element is the response from the SPI target device. Corresponds to the SPI MISO line.

        Raises:
        BackendError: If an exception occurs during the transmission process.
        """

        responses = None
        # Request SPI transfer
        try:
            responses = self.controller.sync_submit([
                lambda transfer_id: self.driver.spiControllerTransfer(id=transfer_id, payload=data, transferLength=transfer_length),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        # Check if the response is of the expected type (by name) and it was successful 
        response_success =  responses[0]["name"] == COMMANDS_DICTIONARY[SPI_CONTROLLER_TRANSFER]["name"] and self.__check_if_response_is_correct(responses[0])
            
        return (response_success, responses[0]["payload"] if response_success else None)