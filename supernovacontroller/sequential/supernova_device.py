import inspect
import os
import queue
import threading

from BinhoSupernova import getConnectedSupernovaDevicesList
from BinhoSupernova.commands.definitions import GetUsbStringSubCommand
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.utils.system_message import SystemOpcode
from transfer_controller import TransferController

from supernovacontroller.errors import (BackendError,
                                        DeviceAlreadyMountedError,
                                        DeviceNotMountedError, DeviceOpenError,
                                        UnknownInterfaceError)

from ..utils.logging import log_instance_method_calls, logging
from .gpio import SupernovaGPIOInterface
from .i2c import SupernovaI2CBlockingInterface
from .i3c import SupernovaI3CBlockingInterface
from .i3c_target import SupernovaI3CTargetBlockingInterface
from .spi_controller import SupernovaSPIControllerBlockingInterface
from .uart import SupernovaUARTBlockingInterface

logger = logging.getLogger("supernovacontroller")

def id_gen(start=0):
    i = start
    while True:
        i += 1
        yield i

class SupernovaDevice:
    def __init__(self, start_id=0):
        self.controller = TransferController(id_gen(start_id))
        self.response_queue = queue.SimpleQueue()
        self.notification_queue = queue.SimpleQueue()
        self.notification_handlers = {}

        self.process_response_thread = threading.Thread(target=self._pull_sdk_response, daemon=True)
        self.process_notifications_thread = threading.Thread(target=self._pull_sdk_notification, daemon=True)

        self.running = True

        self.process_response_thread.start()
        self.process_notifications_thread.start()

        self.driver = Supernova()

        self.interfaces = {
            "i2c": [None, SupernovaI2CBlockingInterface],
            "i3c.controller": [None, SupernovaI3CBlockingInterface],
            "uart": [None, SupernovaUARTBlockingInterface],
            "i3c.target": [None, SupernovaI3CTargetBlockingInterface],
            "spi.controller": [None, SupernovaSPIControllerBlockingInterface],
            "gpio": [None, SupernovaGPIOInterface],
        }

        self.mounted = False

    @property
    def driver(self):
        return self.__driver

    # we override driver setter to wrap with log (if enabled)
    @driver.setter
    def driver(self, newDriver):
        self.__driver = log_instance_method_calls(newDriver, os.environ.get('PYTHON_LOG_PATH') is not None)

    def open(self, usb_address=None):
        if self.mounted:
            raise DeviceAlreadyMountedError

        result = self.driver.open(path=usb_address)
        if result["opcode"] != SystemOpcode.OK.value:
            raise DeviceOpenError(result["message"])

        self.driver.onEvent(self._push_sdk_response)

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.getUsbString(id, getattr(GetUsbStringSubCommand, 'HW_VERSION')),
                lambda id: self.driver.getUsbString(id, getattr(GetUsbStringSubCommand, 'FW_VERSION')),
                lambda id: self.driver.getUsbString(id, getattr(GetUsbStringSubCommand, 'SERIAL_NUMBER')),
                lambda id: self.driver.getUsbString(id, getattr(GetUsbStringSubCommand, 'MANUFACTURER')),
                lambda id: self.driver.getUsbString(id, getattr(GetUsbStringSubCommand, 'PRODUCT_NAME')),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        def _process_device_info(responses):
            hw_version = responses[0]['message'][3:]
            fw_version = responses[1]['message'][3:]
            serial_number = responses[2]['message'][3:]
            manufacturer = responses[3]['message'][3:]
            product_name = responses[4]['message'][3:]

            return {
                "hw_version": hw_version,
                "fw_version": fw_version,
                "serial_number": serial_number,
                "manufacturer": manufacturer,
                "product_name": product_name,
            }

        self.mounted = True

        return _process_device_info(responses)

    @staticmethod
    def getAllConnectedSupernovaDevices():
        return getConnectedSupernovaDevicesList()

    @staticmethod
    def openAllConnectedSupernovaDevices():
        allDevices = SupernovaDevice.getAllConnectedSupernovaDevices()
        openedDevices = []

        for device in allDevices:
            newDevice = SupernovaDevice()
            try:
                newDevice.open(device["path"])
                openedDevices.append(newDevice)
            except DeviceAlreadyMountedError as e:
                continue

        return openedDevices

    def measure_analog_signal(self):
        """
        Measures the voltages found in the different pins of the Supernova.

        Returns:
            tuple: A tuple containing two elements:
                - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
                - The second element is either a dictionary with the measured voltages in mV indicating success, or an error 
                message list detailing the failure messages obtained from the device's response.
                The dictionary is of shape:
                {
                    "i2c_spi_uart_vtarg_mV": Int, 
                    "i3c_high_voltage_vtarg_mV": Int, 
                    "i3c_low_voltage_vtarg_mV": Int,
                }
                All voltage values are measured and presented in milivolts.
        """
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.getAnalogMeasurements(id),
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e
        
        response = responses[0]
        errors = []

        if response["usb_error"] != "CMD_SUCCESSFUL":
            errors.append(response["usb_error"])
        if response["manager_error"] != "SYS_NO_ERROR":
            errors.append(response["manager_error"])
        if response["driver_error"] != "ADC_DRIVER_NO_ERROR":
            errors.append(response["driver_error"])

        if len(errors) > 0:
            return (False, errors)

        return (True, {
            "i2c_spi_uart_vtarg_mV": response["i2c_spi_uart_vtarg_mV"], 
            "i3c_high_voltage_vtarg_mV": response["i3c_high_voltage_vtarg_mV"], 
            "i3c_low_voltage_vtarg_mV": response["i3c_low_voltage_vtarg_mV"],
            })

    def get_hardware_version(self):
        """
        Retrieves the hardware version of the connected Supernova device.

        Returns:
        str: The hardware version of the Supernova device.
        """
        try:
            response = self.controller.sync_submit([
                lambda transfer_id: self.driver.getUsbString(transfer_id, GetUsbStringSubCommand.HW_VERSION)
            ])
            if response[0]["name"] == "GET USB STRING" and "message" in response[0]:
                return response[0]["message"]
        except Exception as e:
            raise BackendError(original_exception=e) from e

        raise BackendError("Unable to retrieve hardware version.")

    def on_notification(self, name, filter_func, handler_func):
        if name not in self.notification_handlers:
            self.notification_handlers[name] = (filter_func, handler_func)

    def _push_sdk_response(self, supernova_response, system_message):
        logger.debug("SDK RESPONSE: supernova_response == %s, system_message == %s", supernova_response, system_message)

        if supernova_response:
            # Check if the id is non-zero (zero is reserved for notifications)
            if supernova_response["id"] != 0:
                # Add the response to the response queue
                self.response_queue.put((supernova_response, system_message))
            else:
                # Add the response to the notification queue for id zero
                self.notification_queue.put((supernova_response, system_message))

    def _pull_sdk_response(self):
        while self.running:
            try:
                supernova_response, system_message = self.response_queue.get(timeout=1)
                self._process_sdk_response(supernova_response, system_message)
            except queue.Empty:
                continue

    def _pull_sdk_notification(self):
        while self.running:
            try:
                supernova_response, system_message = self.notification_queue.get(timeout=1)
                self._process_sdk_notification(supernova_response, system_message)
            except queue.Empty:
                continue

    def _process_sdk_response(self, supernova_response, system_message):
        if supernova_response == None:
            return

        is_handled = self.controller.handle_response(
            transfer_id=supernova_response['id'], response=supernova_response)

        if is_handled:
            return

    def _process_sdk_notification(self, supernova_response, system_message):
        for name, (filter_func, handler_func) in self.notification_handlers.items():
            if filter_func(name, supernova_response):
                handler_func(name, supernova_response)

    def create_interface(self, interface_name):
        if not self.mounted:
            raise DeviceNotMountedError()

        if not interface_name in self.interfaces:
            raise UnknownInterfaceError()

        [interface, interface_class] = self.interfaces[interface_name]

        if interface is None:
            if interface_name == "gpio":
                hardware_version = self.get_hardware_version()
                self.interfaces[interface_name][0] = interface_class(self.driver, self.controller, self.on_notification, hardware_version)
            else:
                self.interfaces[interface_name][0] = interface_class(self.driver, self.controller, self.on_notification)
            interface = self.interfaces[interface_name][0]

        return interface

    def close(self):
        self.driver.close()
        self.running = False
