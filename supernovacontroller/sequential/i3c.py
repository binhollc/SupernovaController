from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.commands.definitions import TransferMode
from BinhoSupernova.commands.definitions import I3cCommandType
from BinhoSupernova.commands.definitions import TransferDirection
from BinhoSupernova.commands.definitions import I3cSetFeatureSelector
from BinhoSupernova.commands.definitions import I3cClearFeatureSelector
from BinhoSupernova.commands.definitions import I3cPushPullTransferRate
from BinhoSupernova.commands.definitions import I3cOpenDrainTransferRate
from BinhoSupernova.commands.definitions import I3cChangeDynAddrError
from supernovacontroller.errors import BusVoltageError
from supernovacontroller.errors import BackendError


class SupernovaI3CBlockingInterface:
    # TODO: Replicate definitions (TransferMode, I3cCommandType, TransferDirection)

    TransferMode = TransferMode
    I3cPushPullTransferRate = I3cPushPullTransferRate
    I3cOpenDrainTransferRate = I3cOpenDrainTransferRate

    BROADCAST_ADDRESS = 0x7E

    def __init__(self, driver: Supernova, controller: TransferController, notification_subscription):
        self.driver = driver
        self.controller = controller

        self.push_pull_clock_freq_mhz = I3cPushPullTransferRate.PUSH_PULL_3_75_MHZ
        self.open_drain_clock_freq_mhz = I3cOpenDrainTransferRate.OPEN_DRAIN_100_KHZ
        self.bus_voltage = None

        self.controller_init()
    
    @staticmethod
    def __get_error_from_response(response : dict):
        errors = []
        if response["usb_result"] != "CMD_SUCCESSFUL":
            errors.append(response["usb_result"]) 
        if response["manager_result"] != "I3C_CONTROLLER_MGR_NO_ERROR":
            errors.append(response["manager_result"]) 
        if "NO_TRANSFER_ERROR" not in response["driver_result"]:
            errors.extend(response["driver_result"]) 
        return errors

    def set_parameters(self, push_pull_clock_freq_mhz: I3cPushPullTransferRate, open_drain_clock_freq_mhz: I3cOpenDrainTransferRate):
        """
        Sets the clock frequencies for push-pull and open-drain configurations using enumerated values.

        This method assigns the provided clock frequencies, selected from predefined enums, to the corresponding attributes of the instance.
        These frequencies are utilized for controlling the operation modes of the device.

        Args:
        push_pull_clock_freq_mhz (I3cPushPullTransferRate): The clock frequency for the push-pull configuration.
                                This is an enumerated value representing specific frequencies defined in the I3C specification.
        open_drain_clock_freq_mhz (I3cOpenDrainTransferRate): The clock frequency for the open-drain configuration.
                                This is an enumerated value representing specific frequencies defined in the I3C specification.

        Note:
        - This method expects values from the I3cPushPullTransferRate and I3cOpenDrainTransferRate enums.
        Passing any other types of values will result in an error.
        - The method directly updates the instance attributes without any further processing or side effects.
        """
        self.push_pull_clock_freq_mhz = push_pull_clock_freq_mhz
        self.open_drain_clock_freq_mhz = open_drain_clock_freq_mhz

        return (True, (self.push_pull_clock_freq_mhz, self.open_drain_clock_freq_mhz))

    def get_parameters(self):
        """
        Retrieves the current clock frequencies for push-pull and open-drain configurations.

        This method returns the values of the push-pull and open-drain clock frequencies that are currently set for the instance.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is an I3cPushPullTransferRate enum value representing the push-pull clock frequency.
                - The second element is an I3cOpenDrainTransferRate enum value representing the open-drain clock frequency.
        """
        return (True, (self.push_pull_clock_freq_mhz, self.open_drain_clock_freq_mhz))

    def set_bus_voltage(self, voltage: int):
        """
        Sets the bus voltage to a specified value.
        The bus voltage of the instance is updated only if the operation is successful.

        Args:
        voltage (int): The voltage value to be set for the I3C bus in mV.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the new bus voltage indicating success, or an error message
                detailing the failure, obtained from the device's response.

        Note:
        - The method assumes that the input voltage value is valid and does not perform any validation.
        Users of this method should ensure that the provided voltage value is within acceptable limits.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.setI3cBusVoltage(id, voltage)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response_ok = responses[0]["name"] == "SET I3C BUS VOLTAGE" and responses[0]["result"] == "SYS_NO_ERROR"
        if response_ok:
            result = (True, voltage)
            # We want to set the bus_voltage when we know the operation was successful
            self.bus_voltage = voltage
        else:
            result = (False, "Set bus voltage failed")
            self.bus_voltage = None

        return result

    def controller_init(self):
        """
        Initialize the Supernova in controller mode.
        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is the result coming from the SDK, or an error message
                detailing the failure, obtained from the device's response.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cControllerInit(id)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]

        return (status == "I3C_CONTROLLER_INIT_SUCCESS", status)

    def init_bus(self, voltage: int=None, targets=None):
        """
        Initialize the bus with a given voltage (in mV) and target devices.

        Args:
        voltage (int, optional): The voltage to initialize the bus with.
                                Defaults to None, in which case the existing
                                bus voltage is used.
        targets (dict, optional): A dictionary where each key is an integer device identifier, and each value
                                is a dictionary containing device properties. The device properties include:
                                - 'staticAddress' (int): The static address of the device.
                                - 'dynamicAddress' (int): The dynamic address of the device.
                                - 'bcr' (int): Bus Characteristic Register value.
                                - 'dcr' (int): Device Characteristic Register value.
                                - 'pid' (list of int): An array of bytes representing the Product ID.
                                - 'maxIbiPayloadLength' (int): Maximum length of the IBI payload.
                                - 'i3cFeatures' (various): I3C features supported by the device.

        Raises:
        BusVoltageError: If 'voltage' is not provided or bus voltage was not set.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the bus voltage indicating success, or an error message
                detailing the failure, obtained from the device's response.

        Note:
        - The method assumes that the input voltage value is valid and does not perform any validation.
        Users of this method should ensure that the provided voltage value is within acceptable limits.
        - The 'targets' dictionary structure should match the provided format for proper operation.
        """

        if voltage is None:
            if self.bus_voltage is None:
                raise BusVoltageError()
            voltage = self.bus_voltage
        else:
            (success, set_bus_voltage_result) = self.set_bus_voltage(voltage)
            if not success:
                return (False, set_bus_voltage_result)

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cInitBus(id, targets)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # TODO: Toggle IBIs off

        status = responses[0]["result"]
        if status == "DAA_SUCCESS" and "NO_TRANSFER_ERROR" in responses[0]["errors"]:
            result = (True, voltage)
        else:
            result = (False, {"errors": responses[0]["result"]})

        return result

    def reset_bus(self):
        """
        Resets the I3C bus to its default state.

        It is typically used to reset the bus to a known state, clearing any configurations or settings
        that might have been applied during the operation of the device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the bus voltage indicating success, or an error message
                detailing the failure, obtained from the device's response.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cClearFeature(id, I3cClearFeatureSelector.I3C_BUS, self.BROADCAST_ADDRESS)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]
        if status == "I3C_CLEAR_FEATURE_SUCCESS":
            result = (True, self.bus_voltage)
        else:
            result = (False, responses[0]["errors"])

        return result

    def targets(self):
        """
        Retrieves the target device table from the I3C bus.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a list of dictionaries, or an error message detailing the failure,
                obtained from the device's response.
                Each dictionary entry contains formatted information about the device, including:
                - 'static_address': The static address in hexadecimal format.
                - 'dynamic_address': The dynamic address in hexadecimal format.
                - 'bcr': The Bus Characteristics Register value.
                - 'dcr': The Device Characteristics Register.
                - 'pid': Unique ID (Provisional ID) containing a manufacturer ID, a part ID and an instance ID.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGetTargetDeviceTable(id)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # Note: Borrowed from MissionControlBridge's Supernova Adaptor
        targets = []
        for target_info in responses[0]["table"]:
            static_address = target_info["staticAddress"]
            dynamic_address = target_info["dynamicAddress"]
            bcr = int(target_info["bcr"]["value"][2][2:4], 16)
            dcr = target_info["dcr"]
            pid = target_info["pid"]
            formatted_target_info = {
                "static_address" : static_address,
                "dynamic_address" : dynamic_address,
                "bcr" : bcr,
                "dcr" : dcr,
                "pid" : pid
            }

            targets.append(formatted_target_info)

        # TODO: Error cases
        result = (True, targets)

        return result

    def find_target_device_by_pid(self, pid):
        """
        Retrieves the target device from the I3C bus with the specified PID.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary, or an error message detailing the failure,
                obtained from the device's response.
                The dictionary entry contains formatted information about the device, including:
                - 'static_address': The static address in hexadecimal format.
                - 'dynamic_address': The dynamic address in hexadecimal format.
                - 'bcr': The Bus Characteristics Register value.
                - 'dcr': The Device Characteristics Register.
                - 'pid': Unique ID (Provisional ID) containing a manufacturer ID, a part ID and an instance ID.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGetTargetDeviceTable(id)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        filtered_devices = list(filter(lambda device: device["pid"] == pid, responses[0]["table"]))

        if (len(filtered_devices) == 0):
            return (False, None)
        
        target_info = filtered_devices[0]
        static_address = target_info["staticAddress"]
        dynamic_address = target_info["dynamicAddress"]
        bcr = int(target_info["bcr"]["value"][2][2:4], 16)
        dcr = target_info["dcr"]
        pid = target_info["pid"]
        return (True, {
            "static_address" : static_address,
            "dynamic_address" : dynamic_address,
            "bcr" : bcr,
            "dcr" : dcr,
            "pid" : pid
        })

    def toggle_ibi(self, target_address, enable: bool):
        """
        Toggles the In-Band Interrupt (IBI) feature for a specified target device on the I3C bus.

        This method either enables or disables the IBI feature for the device at the given address,
        based on the 'enable' flag.

        Args:
        target_address: The address of the target device on the I3C bus. This should be a valid address
                        corresponding to a device connected to the bus.
        enable (bool, optional): A flag indicating whether to enable (True) or disable (False) the IBI
                                feature.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the string "OK" indicating success, or an error message
                detailing the failure, obtained from the controller's response.
        """
        if enable:
            seq = [ lambda id: self.driver.i3cSetFeature(id, I3cSetFeatureSelector.REGULAR_IBI, target_address) ]
        else:
            seq = [ lambda id: self.driver.i3cClearFeature(id, I3cClearFeatureSelector.REGULAR_IBI, target_address) ]

        try:
            responses = self.controller.sync_submit(seq)
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]
        if status == "I3C_SET_FEATURE_SUCCESS" or status == "I3C_CLEAR_FEATURE_SUCCESS":
            result = (True, "OK")
        else:
            result = (False, responses[0]["errors"])

        return result

    def target_update_address(self, current_address, new_address):
        """
        Updates the dynamic address of a target device on the I3C bus.

        This method sends a command to the target device to change its dynamic address from a current
        address to a new address. It checks the operation's success status and returns a tuple
        indicating whether the operation was successful and either a confirmation message or error details.

        Args:
        current_address: The current dynamic address of the target device. This should be the address
                        that the device is currently using on the I3C bus.
        new_address: The new dynamic address to be assigned to the target device. This is the address
                    that the device will use on the I3C bus after successful execution of this command.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the string "OK" indicating success, or an error message
                detailing the failure, obtained from the controller's response.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cChangeDynamicAddress(id, current_address, new_address)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]

        if status == I3cChangeDynAddrError.I3C_CHANGE_DYNAMIC_ADDRESS_SUCCESS:
            result = (True, "OK")
        else:
            result = (False, status)

        return result

    def trigger_target_reset_pattern(self):
        """
        Triggers the target reset pattern on the I3C bus.

        It indicates the targets to execute the reset action configured via the RSTACT CCC.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either None indicating success, or an error message
                detailing the failure, obtained from the device's response.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTriggerTargetResetPattern(id)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response = responses[0]
        errors = self.__get_error_from_response(response)

        if len(errors) == 0: # manager, usb and driver are without error
            result = (True, None)
        else:
            result = (False, errors)

        return result

    def trigger_exit_pattern(self):
        """
        Triggers the HDR exit pattern on the I3C bus.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either None indicating success, or an error message
                detailing the failure, obtained from the device's response.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTriggerExitPattern(id)
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        response = responses[0]
        errors = self.__get_error_from_response(response)

        if len(errors) != 0: # manager, usb and/or driver have error
            return (False, errors)

        return (True, None)

    def _process_response(self, command_name, responses, extra_data=None):
        def format_successful_response_payload(command_name, response):
            if command_name == "write":
                return None
            elif command_name == "read":
                return response["data"]
            elif command_name == "ccc_getpid":
                return [int(item[2:], 16) for item in response["pid"]]
            elif command_name == "ccc_getbcr":
                return response["bcr"]["value"][2][2:].upper()
            elif command_name == "ccc_getdcr":
                return response["dcr"][2:].upper()
            elif command_name == "ccc_getmrl":
                return response["maxReadLength"]
            elif command_name == "ccc_getmwl":
                return response["maxWriteLength"]
            elif command_name == "ccc_getxtime":
                return {
                 "supportedModes": response["supportedModes"]["value"][1],
                 "currentState": response["state"]["value"][1],
                 "frequency": response["frequency"]["value"],
                 "inaccuracy": response["inaccuracy"]["value"],
                }
            elif command_name == "ccc_getmxds":
                return {
                 "maxWrite": response["maxWr"]["value"][1],
                 "maxRead": response["maxRd"]["value"][1],
                 "maxReadTurnaround": float(response["maxRdTurn"][1].split(" ")[0]),
                }
            elif command_name == "ccc_getcaps":
                return [
                    response["caps1"]["value"][1],
                    response["caps2"]["value"][1],
                    response["caps3"]["value"][1],
                    response["caps4"]["value"]
                ]
            elif command_name == "ccc_get_status":
                return response["data"]
            elif command_name in ["ccc_setnewda", "ccc_rstdaa"]:
                return None
            elif command_name == "ccc_direct_rstact":
                return response["data"] if response["descriptor"] and response["descriptor"]["dataLength"] > 0 else None
            elif command_name in ["ccc_unicast_setmrl", "ccc_unicast_setmwl", "ccc_broadcast_setmwl", "ccc_broadcast_setmrl"]:
                return response["data"]
            return None
        def format_error_response_payload(command_name, response):
            error_data = None
            if command_name in ["ccc_setaasa", "ccc_setdasa", "ccc_entdaa"]:
                if (response['invalidAddresses']):
                    error_data = response['invalidAddresses']
                result = {"error": response["header"]["result"]}
                if error_data: result["error_data"] = error_data
                return result

            return response["descriptor"]["errors"][0]

        response = responses[0]
        success = response["header"]["result"] == "I3C_TRANSFER_SUCCESS" or response["header"]["result"] == "DAA_SUCCESS"

        if success:
            data = format_successful_response_payload(command_name, response)
        else:
            data = format_error_response_payload(command_name, response)

        if extra_data:
            data.update(extra_data)

        return (success, data)

    def write(self, target_address, mode: TransferMode, subaddress: [], buffer: list):
        """
        Performs a write operation to a target device on the I3C bus.

        This method sends data to the specified target device. It includes various parameters like the target
        address, transfer mode, and data to be written. It checks the operation's success status and returns
        a tuple indicating whether the operation was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which data is to be written.
        mode (TransferMode): The transfer mode to be used for the write operation. This should be an instance
                            of the TransferMode enum, indicating the desired transfer mode.
        subaddress (list): A list of integers representing the subaddress to be used in the write operation.
        buffer (list): A list of data bytes to be written to the target device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the data written and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cWrite(
                    id,
                    target_address,
                    mode,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    subaddress,
                    buffer,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("write", responses)

    def read(self, target_address, mode: TransferMode, subaddress: [], length):
        """
        Performs a read operation from a target device on the I3C bus.

        This method reads data from the specified target device using a given transfer mode, subaddress,
        and expected length of data. It sends the appropriate command to the controller and processes the
        response, returning either the successfully read data or an error message.

        Args:
        target_address: The address of the target device on the I3C bus from which data is to be read.
        mode (TransferMode): The transfer mode to be used for the read operation. This should be an instance
                            of the TransferMode enum, indicating the desired transfer mode.
        subaddress (list): A list of integers representing the subaddress to be used in the read operation.
        length (int): The expected length of data to be read from the device, specified as an integer.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the read data and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cRead(
                    id,
                    target_address,
                    mode,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    subaddress,
                    length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("read", responses)

    def ccc_getbcr(self, target_address):
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETBCR(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getbcr", responses)

    def ccc_getdcr(self, target_address):
        """
        Performs a GETDCR (Get Device Characteristics Register) operation on a target device on the I3C bus.

        This method requests the Device Characteristics Register (DCR) data from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the DCR data is requested.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the DCR data and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETDCR(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getdcr", responses)

    def ccc_getpid(self, target_address):
        """
        Performs a GETPID (Get Provisional ID) operation on a target device on the I3C bus.

        This method requests the Provisional ID (PID) data from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the PID data is requested.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the PID data and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETPID(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getpid", responses)

    def ccc_getacccr(self, target_address):
        """
        Performs a GETACCCR (Get Acceptable Command Codes Register) operation on a target device on the I3C bus.

        This method requests the Acceptable Command Codes Register (ACCCR) data from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the ACCCR data is requested.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the ACCCR data and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETACCCR(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getacccr", responses)

    def ccc_direct_rstact(self, target_address, defining_byte, read_or_write_reset_action):
        """
        Performs a DIRECT RSTACT (Target Reset Action) operation on a target device on the I3C bus.

        This method is used to configure the next Target Reset action, and may be used to retrieve a Target's 
        reset recovery timing or get the reset action of the target. 
        The RSTACT CCC is used in conjunction with the Target Reset Pattern to reset targets.

        Args:
        target_address (c_uint8): The dynamic address of the target device. 
            This should be the address that the device is currently using on the I3C bus.
        defining_byte (I3cTargetResetDefByte): The defining byte used for the RSTACT CCC.
        read_or_write_reset_action (TransferDirection): Determines whether to read or write the reset action.
            It should be either TransferDirection.WRITE or TransferDirection.READ.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element depends on the read_or_write_reset_action value:
                - If it is a write, then the returned value can be either None indicating success, 
                    or an error message detailing the failure obtained from the controller's response.
                - If it is a read, the returned value is the reset action in case of success,
                    or an error message detailing the failure obtained from the controller's response. 
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectRSTACT(
                    id,
                    target_address,
                    defining_byte,
                    read_or_write_reset_action,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_direct_rstact", responses)

    def ccc_broadcast_rstact(self, defining_byte):
        """
        Performs a BROADCAST RSTACT (Target Reset Action) set operation on the I3C bus.

        This method is used to configure the next Target Reset action on all targets.
        The RSTACT CCC is used in conjunction with the Target Reset Pattern to reset targets.

        Args:
        defining_byte (I3cTargetResetDefByte): The defining byte used for the RSTACT CCC.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is None if the operation was succesful, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastRSTACT(
                    id,
                    defining_byte,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_rstact", responses)

    def ccc_getmxds(self, target_address):
        """
        Performs a GETMXDS (Get Max Data Speed) operation on a target device on the I3C bus.

        This method requests the Maximum Data Speed information from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the Max Data Speed information is requested.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
                - The second element is either a dictionary containing the Max Data Speed information bytes as int and the Turn Around as float in ms,
                or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETMXDS(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getmxds", responses)

    def ccc_getmrl(self, target_address):
        """
        Performs a GETMRL (Get Maximum Read Length) operation on a target device on the I3C bus.

        This method requests the Maximum Read Length information from the specified target device.
        The success of the operation is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the Max Read Length information is requested.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the Max Read Length information and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETMRL(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getmrl", responses)

    def ccc_getmwl(self, target_address):
        """
        Performs a GETMWL (Get Maximum Write Length) operation on a target device on the I3C bus.

        This method requests the Maximum Write Length information from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the Maximum Write Length information is requested.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either a dictionary containing the Maximum Write Length information and its length, indicating
                success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETMWL(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getmwl", responses)

    def ccc_getxtime(self, target_address):
        """
        Performs a GETXTIME (Get Extra Timing Information) operation on a target device on the I3C bus.

        This method requests the Extra Timing Information from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the Extra Timing Information is requested.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
                - The second element is either a dictionary containing the Extra Timing Information Bytes as int, indicating
                    success, or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETXTIME(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getxtime", responses)

    def ccc_getcaps(self, target_address):
        """
        Performs a GETCAPS (Get Capabilities) operation on a target device on the I3C bus.

        This method requests the Capabilities information from the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus from which the Capabilities information is requested.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
                - The second element is either a list with the CAP byte values (as ints) ordered ascendingly, 
                or an error message detailing the failure.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETCAPS(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_getcaps", responses)

    def ccc_rstdaa(self):
        """
        Performs a RSTDAA (Reset Dynamic Address Assignment) operation on a target device on the I3C bus.

        This method initiates a Reset Dynamic Address Assignment process on the specified target device.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Since RSTDAA does not typically return data, only success or failure is indicated.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cRSTDAA(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_rstdaa", responses)

    def ccc_entdaa(self, device_table : dict):
        """
        Performs a broadcast ENTDAA (Enter Dynamic Address Assignment) operation on the I3C Bus.

        This CCC indicates to all I3C Devices to enter the Dynamic Address Assignment procedure.
        Target Devices that already have a Dynamic Address assigned shall not respond to this command.

        Args:
            device_table: A dictionary of the shape:  
            ```  
            {
                "static_address" : static_address,
                "dynamic_address" : dynamic_address,
                "bcr" : bcr,
                "dcr" : dcr,
                "pid" : pid
            }  
            ```

        Returns:
            tuple: A tuple containing two elements:
                - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
                - The second element is either an error message detailing the failure or a success message.
                Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cENTDAA(
                    id,
                    device_table
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_entdaa", responses)

    def ccc_broadcast_enec(self, events: list):
        """
        Performs a broadcast ENEC (Enable Events Command) operation on the I3C bus.

        This method sends a broadcast command to enable events on all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        events (list): A list of events to be enabled. Each element in the list must be an instance
                   of the ENEC enum, which includes the following options:
                   - ENEC.ENINT
                   - ENEC.ENCR
                   - ENEC.ENHJ
                   For example: [ENEC.ENINT, ENEC.ENHJ]

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Since this is a broadcast command, no specific data is expected in return.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENEC(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    events
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # Note: The command name 'ccc_broadcast_ENEC' should be handled appropriately in _process_response
        return self._process_response("ccc_broadcast_enec", responses)

    def ccc_broadcast_disec(self, events: list):
        """
        Performs a broadcast DISEC (Disable Events Command) operation on the I3C bus.

        This method sends a broadcast command to disable events on all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        events (list): A list containing events to be disabled. Each element in the list must be an instance
                   of the DISEC enum, which includes the following options:
                   - DISEC.DISINT
                   - DISEC.DISCR
                   - DISEC.DISHJ
                   For example: [DISEC.DISINT, DISEC.DISHJ]

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Since this is a broadcast command, no specific data is expected in return.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastDISEC(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    events
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        # Note: The command name 'ccc_broadcast_DISEC' should be handled appropriately in _process_response
        return self._process_response("ccc_broadcast_disec", responses)

    def ccc_unicast_enec(self, target_address, events: list):
        """
        Performs a unicast ENEC (Enable Events Command) operation on a specific target device on the I3C bus.

        This method sends a command to enable events on a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the ENEC command is directed.
        events (list): A list of events to be enabled. Each element in the list must be an instance
                   of the ENEC enum, which includes the following options:
                   - ENEC.ENINT
                   - ENEC.ENCR
                   - ENEC.ENHJ
                   For example: [ENEC.ENINT, ENEC.ENHJ]

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectENEC(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    events
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_enec", responses)

    def ccc_unicast_disec(self, target_address, events: list):
        """
        Performs a unicast DISEC (Disable Events Command) operation on a specific target device on the I3C bus.

        This method sends a command to disable events on a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the DISEC command is directed.
        events (list): A list containing events to be disabled. Each element in the list must be an instance
                   of the DISEC enum, which includes the following options:
                   - DISEC.DISINT
                   - DISEC.DISCR
                   - DISEC.DISHJ
                   For example: [DISEC.DISINT, DISEC.DISHJ]

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectDISEC(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    events
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_disec", responses)

    def ccc_setdasa(self, static_address, dynamic_address):
        """
        Performs a SETDASA (Set Dynamic Address for Static Address) operation on the I3C bus.

        This method sets a dynamic address for a device with a known static address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        static_address: The static address of the target device on the I3C bus.
        dynamic_address: The dynamic address to be assigned to the target device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cSETDASA(
                    id,
                    static_address,
                    dynamic_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_setdasa", responses)

    def ccc_setnewda(self, current_address, new_address):
        """
        Performs a SETNEWDA (Set New Dynamic Address) operation on the I3C bus.

        This method updates the dynamic address of a device currently on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        current_address: The current dynamic address of the target device on the I3C bus.
        new_address: The new dynamic address to be assigned to the target device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cSETNEWDA(
                    id,
                    current_address,
                    new_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_setnewda", responses)

    def ccc_unicast_setgrpa(self, target_address):
        """
        Performs a unicast SETGRPA (Set Group Address) operation on a specific target device on the I3C bus.

        This method sends a command to set the group address of a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the SETGRPA command is directed.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectSETGRPA(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_setgrpa", responses)

    def ccc_unicast_rstgrpa(self, target_address):
        """
        Performs a unicast RSTGRPA (Reset Group Address) operation on a specific target device on the I3C bus.

        This method sends a command to reset the group address of a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the RSTGRPA command is directed.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectRSTGRPA(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_rstgrpa", responses)

    def ccc_unicast_setmrl(self, target_address, max_read_length):
        """
        Performs a unicast SETMRL (Set Maximum Read Length) operation on a specific target device on the I3C bus.

        This method sends a command to set the maximum read length for a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the SETMRL command is directed.
        max_read_length: The maximum read length to be set for the target device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectSETMRL(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    max_read_length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_setmrl", responses)

    def ccc_unicast_setmwl(self, target_address, max_write_length):
        """
        Performs a unicast SETMWL (Set Maximum Write Length) operation on a specific target device on the I3C bus.

        This method sends a command to set the maximum write length for a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the SETMWL command is directed.
        max_write_length: The maximum write length to be set for the target device.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectSETMWL(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    max_write_length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_setmwl", responses)

    def ccc_broadcast_setmwl(self, max_write_length):
        """
        Performs a broadcast SETMWL (Set Maximum Write Length) operation on the I3C bus.

        This method sends a broadcast command to set the maximum write length for all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        max_write_length: The maximum write length to be set for all devices on the I3C bus.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastSETMWL(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    max_write_length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_setmwl", responses)

    def ccc_broadcast_setmrl(self, max_read_length):
        """
        Performs a broadcast SETMRL (Set Maximum Read Length) operation on the I3C bus.

        This method sends a broadcast command to set the maximum read length for all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        max_read_length: The maximum read length to be set for all devices on the I3C bus.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastSETMWL(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    max_read_length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_setmrl", responses)

    def ccc_setaasa(self, static_addresses : list[int]):
        """
        Performs a broadcast SETAASA (Set All Agents to Static Address) operation on the I3C bus.

        This method sends a broadcast command to set all agents on the I3C bus to a static address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        static_addresses: A list of the static addresses to update the internal device table.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cSETAASA(
                    id,
                    static_addresses,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_setaasa", responses)

    def ccc_broadcast_endxfed(self):
        """
        Performs a broadcast ENDXFED (End Extra Fast-Mode Device Exchange) operation on the I3C bus.

        This method sends a broadcast command to signal the end of an extra fast-mode data exchange period on all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENDXFED(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_endxfed", responses)

    def ccc_unicast_endxfer(self, target_address):
        """
        Performs a unicast ENDXFER (End Transfer) operation on a specific target device on the I3C bus.

        This method sends a command to end a data transfer operation for a specific target device identified by its address.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
        target_address: The address of the target device on the I3C bus to which the ENDXFER command is directed.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cDirectENDXFER(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_unicast_endxfer", responses)

    def ccc_broadcast_setxtime(self, timing_parameter, aditional_data = []):
        """
        Performs a broadcast SETXTIME (Set Exchange Timing) operation on the I3C bus.

        This method sends a broadcast command to configure exchange timing parameters for all devices on the I3C bus.
        The operation's success status is checked, and it returns a tuple indicating whether the operation
        was successful along with the relevant data or error message.

        Args:
            timing_parameter: The exchange timing parameter to be set for all devices on the I3C bus, A.K.A. the SubCommand Byte.
            aditional_data (optional): Additional data bytes which may be neccesary for certains Sub-Commands.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastSETXTIME(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    timing_parameter,
                    aditional_data
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_setxtime", responses)

    def ccc_unicast_setxtime(self, target_address):
        pass # TODO see issue BMC2-1662

    def ccc_broadcast_setbuscon(self, context: int, data: list = []):
        """
        Performs a broadcast SETBUSCON (Set Bus Configuration) operation on the I3C bus.

        This method sends a broadcast command to set a particular context on the bus, which could be a higher-level protocol
        specification or a version of the MIPI I3C Specification. This context is used to activate special functionalities
        required to support the selected protocol on the bus.

        Args:
        context: An integer representing the context for the bus configuration. This could indicate a higher-level
                 protocol or a specific version of the MIPI I3C Specification.
        data: An optional list of data items relevant to the bus configuration.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message.
              Specific data is usually not returned in this operation, only the success or failure status.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastSETBUSCON(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                    context,
                    data
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_setbuscon", responses)

    def ccc_broadcast_entas0(self):
        """
        Performs a broadcast ENTAS0 (Enter Activity State 0) operation on the I3C bus.

        This method sends a broadcast command to inform all devices on the I3C bus to enter Activity State 0,
        where the bus is expected to be idle for 1 microsecond (us). It is part of an activity state series
        (ENTAS0 to ENTAS3) that devices can use for power management, specifically to manage low power states during idle periods.

        The ENTAS0 command acts as a suggestion rather than a directive, allowing devices to prepare for a
        low-power state without overriding any specific or custom power-saving agreements that might be
        implemented at the application level.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message,
              reflecting the broadcast command's attempt to set the bus to the specified idle time.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENTAS0(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_entas0", responses)

    def ccc_broadcast_entas1(self):
        """
        Sends a broadcast ENTAS1 command to all devices on the I3C bus, indicating that the bus will enter
        an idle state for 100 microseconds (us). This command is part of power management strategies to
        reduce power consumption during known periods of inactivity.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message,
              reflecting the broadcast command's attempt to set the bus to the specified idle time.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENTAS1(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_entas1", responses)

    def ccc_broadcast_entas2(self):
        """
        Sends a broadcast ENTAS2 command to all devices on the I3C bus, indicating that the bus will enter
        an idle state for 2 milliseconds (ms). This command is part of power management strategies to
        reduce power consumption during known periods of inactivity.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message,
              reflecting the broadcast command's attempt to set the bus to the specified idle time.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENTAS2(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_entas2", responses)

    def ccc_broadcast_entas3(self):
        """
        Sends a broadcast ENTAS3 command to all devices on the I3C bus, indicating that the bus will enter
        an idle state for 50 milliseconds (ms). This command is part of power management strategies to
        reduce power consumption during known periods of inactivity.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either an error message detailing the failure or a success message,
              reflecting the broadcast command's attempt to set the bus to the specified idle time.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cBroadcastENTAS3(
                    id,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_broadcast_entas3", responses)

    def ccc_unicast_get_status(self, target_address):
        """
        Sends a unicast GET_STATUS command to the device with target_address dynamic address

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is the two bytes that represent the status.

        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cGETSTATUS(
                    id,
                    target_address,
                    self.push_pull_clock_freq_mhz,
                    self.open_drain_clock_freq_mhz,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        return self._process_response("ccc_get_status", responses)
    