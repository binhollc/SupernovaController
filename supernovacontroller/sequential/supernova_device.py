from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.commands.definitions import GetUsbStringSubCommand
from supernovacontroller.errors import DeviceOpenError
from supernovacontroller.errors import DeviceNotMountedError
from supernovacontroller.errors import UnknownInterfaceError
from supernovacontroller.errors import BackendError
import queue
import threading
from .i2c import SupernovaI2CBlockingInterface
from .i3c import SupernovaI3CBlockingInterface

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

      self.process_response_thread = threading.Thread(target=self._pull_sdk_response, daemon=True)
      self.running = True
      self.process_response_thread.start()
      self.driver = Supernova()

      self.interfaces = {
          "i2c": [None, SupernovaI2CBlockingInterface],
          "i3c.controller": [None, SupernovaI3CBlockingInterface],
      }

      self.mounted = False

    def open(self, usb_address=None):
        result = self.driver.open(path=usb_address, activateLogger=False)
        if result["code"] == "OPEN_CONNECTION_FAIL":
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

    def _push_sdk_response(self, supernova_response, system_message):
        self.response_queue.put((supernova_response, system_message))

    def _pull_sdk_response(self):
        while self.running:
            try:
                supernova_response, system_message = self.response_queue.get(timeout=1)
                self._process_sdk_response(supernova_response, system_message)
            except queue.Empty:
                continue

    def _process_sdk_response(self, supernova_response, system_message):
        if supernova_response == None:
            return

        is_handled = self.controller.handle_response(
            transfer_id=supernova_response['id'], response=supernova_response)

        if is_handled:
            return

        if supernova_response["name"] == "I3C TRANSFER":
            self.notification_queue.put((supernova_response, system_message))

        # Process non-sequenced responses
        # ...

    def create_interface(self, interface_name):
        if not self.mounted:
            raise DeviceNotMountedError()

        if not interface_name in self.interfaces:
            raise UnknownInterfaceError()

        [interface, interface_class] = self.interfaces[interface_name]

        if interface is None:
            self.interfaces[interface_name][0] = interface_class(self.driver, self.controller)
            interface = self.interfaces[interface_name][0]

        return interface

    def close(self):
        self.driver.close()
        self.running = False


