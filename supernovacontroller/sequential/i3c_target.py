from transfer_controller import TransferController
from BinhoSupernova.Supernova import Supernova
from BinhoSupernova.commands.definitions import (I3cTargetMemoryLayout_t, I3cTargetMaxDataSpeedLimit_t, I3cTargetIbiCapable_t, I3cTargetIbiPayload_t, 
                                                 I3cTargetOfflineCap_t, I3cTargetVirtSupport_t, I3cTargetDeviceRole_t, I3cTargetDcr_t)
from supernovacontroller.errors import BusVoltageError
from supernovacontroller.errors import BusNotInitializedError
from supernovacontroller.errors import BackendError
from threading import Event
import queue

class I3CTargetNotificationHandler:

    def __init__(self,notification_subscription):
        """
        Initializes the I3CTargetNotificationHandler.

        Args:
        notification_subscription: A subscription object for receiving notifications.

        Note:
        The notification_subscription parameter is used to set up the subscription
        for handling I3C notifications within the handler.
        """

        self.notification = Event()
        self.notification_message = None
        self.modified = False
        notification_subscription("I3C TARGET NOTIFICATION", filter_func=self.is_i3c_target_notification, handler_func=self.handle_i3c_target_notification)
        # High level notification handling queue to pass message from handle_i3c_target_notification to wait_for_notification
        self.high_notification_queue = queue.SimpleQueue()

    def wait_for_notification(self, timeout):
        """
        Waits for a I3C Target notification.

        This method waits for a I3C Target notification for a specified duration.

        Args:
        timeout: The duration in seconds to wait for the notification.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of receiving the notification.
            - The second element is either the received message if successful or None if no notification is received.

        Note:
        While testing, it was noted that sometimes the I3C notification can be received before the user calls to wait_for_notification,
        so i3c_notification does not see the set event. By adding the modified, wait_for_notification function checks if an event 
        already occurred and just returns its associated message in that case. 
        """

        data_has_been_received = False
        if self.high_notification_queue.empty():
            data_has_been_received = self.notification.wait(timeout)
            self.notification.clear()
            if (data_has_been_received is False):
                self.notification_message = None
            else:
                self.notification_message = self.high_notification_queue.get()
        else:
            data_has_been_received = True
            self.notification_message = self.high_notification_queue.get()

        return data_has_been_received, self.notification_message
    
    def is_i3c_target_notification(self, name, message):
        """
        Checks if the received notification is sent by the I3C target.

        Args:
        name: The name of the received notification.
        message: The content of the received notification.

        Returns:
        bool: True if the notification is related to the I3C target mode, False otherwise.
        """
 
        # Hot-Fix to solve extra space in the firmware release
        if message["name"] != "I3C TARGET NOTIFICATION":
            return False
        return True
    
    def handle_i3c_target_notification(self, name, message):
        """
        This method handles the I3C received notification by setting the received message and
        triggering the notification event.

        Args:
        name: The name of the received notification.
        message: The content of the received notification.

        Note:
        While testing, it was noted that sometimes the I3C notification can be received before the user calls to wait_for_notification, so
        i3c_notification does not see the set event. By adding the modified flag, handle_i3c_target_notification indicates to 
        wait_for_notification function that an event was raised before it was called.
        """
        self.notification_message = message
        self.high_notification_queue.put(message)
        self.notification.set()
        
class SupernovaI3CTargetBlockingInterface:
    
    def __init__(self, driver: Supernova, controller: TransferController, notification_subscription):
        self.driver = driver
        self.controller = controller
        self.mem_layout = I3cTargetMemoryLayout_t.MEM_2_BYTES
        # I3C target notification handler
        self.i3c_notification = I3CTargetNotificationHandler(notification_subscription)
        self.voltage = None

 
    def target_init(self, memory_layout: I3cTargetMemoryLayout_t, useconds_to_wait_for_ibi, max_read_length, max_write_length, features):
        """
        Initialize the I3C peripheral in target mode.

        Args:
        memory_layout (I3cTargetMemoryLayout_t): Layout of the memory that the target represents.
        useconds_to_wait_for_ibi (int): Micro seconds to allow an In-Band Interrupt (IBI) to drive SDA low when the controller is not doing so.
        max_read_length (int): Maximum read length that the user wants the Supernova to handle.
        max_write_length (int) : Maximum write length that the user wants the Supernova to handle.
        features (int): Series of flags that describe the features of the Supernova in target mode.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetInit(
                    id,
                    memory_layout,
                    useconds_to_wait_for_ibi,
                    max_read_length,
                    max_write_length,
                    features,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]
        return (status == "I3C_TARGET_INIT_SUCCESS", status)

    def set_voltage(self, voltage: int):
        """
        Sets the voltage to a specified value.
        The voltage of the instance is updated only if the operation is successful.

        Args:
        voltage (int): The voltage value to be set in mV.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the new voltage indicating success, or an error message
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
            self.voltage = voltage
        else:
            result = (False, "Set bus voltage failed")
            self.voltage = None

        return result

    def set_pid(self, pid: list):
        """
        Modifies the PID of the I3C target via USB.

        Args:
        pid (list): PID to set by the user, PID[0] is the LSB.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetSetPid(
                    id,
                    pid,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]
        return (status == "I3C_TARGET_SET_PID_SUCCESS", status)    

    def set_bcr(self, max_data_speed_limit: I3cTargetMaxDataSpeedLimit_t, ibi_req_capable: I3cTargetIbiCapable_t, ibi_payload: I3cTargetIbiPayload_t, offline_capable: I3cTargetOfflineCap_t, virt_targ_support: I3cTargetVirtSupport_t, device_role: I3cTargetDeviceRole_t):
        """
        Modifies the BCR of the I3C target via USB. 
        Note: BCR[5] which indicates advanced capabilities (in this case HDR DDR mode) is a a read-only bit, always set by the peripheral.
        
        Args:
        max_data_speed_limit (I3cTargetMaxDataSpeedLimit_t): Indicates if there is a data speed limit.
        ibi_req_capable (I3cTargetIbiCapable_t): Shows if the target is capable of requesting IBIs.
        ibi_payload (I3cTargetIbiPayload_t): Shows if the target is capable of sending data during IBIs.
        offline_capable (I3cTargetOfflineCap_t) : Specifies wether the target has offline capabilities or not.
        virt_targ_support (I3cTargetVirtSupport_t): Indicates if the target supports virtual target mode.
        device_role (I3cTargetDeviceRole_t): Specifies the role.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetSetBcr(
                    id,
                    max_data_speed_limit,
                    ibi_req_capable,
                    ibi_payload,
                    offline_capable,
                    virt_targ_support,
                    device_role,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        result = (responses[0]["usb_result"]) and (responses[0]["manager_result"]) and (responses[0]["driver_result"])
        status = "I3C_TARGET_SET_BCR_SUCCESS" if result else "I3C_TARGET_SET_BCR_FAILED"
        return (result, status)    

    def set_dcr(self, dcr_value: I3cTargetDcr_t):
        """
        Modifies the DCR of the I3C target via USB

        Args:
        dcr_value (I3cTargetType_t): Determines the type of device the target represents which defines the DCR.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetSetDcr(
                    id,
                    dcr_value,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        result = (responses[0]["usb_result"]) and (responses[0]["manager_result"]) and (responses[0]["driver_result"])
        status = "I3C_TARGET_SET_DCR_SUCCESS" if result else "I3C_TARGET_SET_DCR_FAILED"
        return (result, status)    

    def set_static_address(self, staticAddr):
        """
        Modifies the static address of the I3C target via USB

        Args:
        staticAddr (int): Static address to assign.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetSetStaticAddr(
                    id,
                    staticAddr,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        result = (responses[0]["usb_result"]) and (responses[0]["manager_result"]) and (responses[0]["driver_result"])
        status = "I3C_TARGET_SET_STATIC_ADDRESS_SUCCESS" if result else "I3C_TARGET_SET_STATIC_ADDRESS_FAILED"
        return (result, status)    

    def set_configuration(self, useconds_to_wait_for_ibi, max_read_length, max_write_length, features):
        """
        Configures the I3C peripheral in target mode.

        Args:
        useconds_to_wait_for_ibi (int): Micro seconds to allow an In-Band Interrupt (IBI) to drive SDA low when the controller is not doing so.
        max_read_length (int): Maximum read length that the user wants the Supernova to handle.
        max_write_length (int) : Maximum write length that the user wants the Supernova to handle.
        features (int): Series of flags that describe the features of the Supernova in target mode.

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is a message indicating the success or failure of the operation
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetSetConfiguration(
                    id,
                    useconds_to_wait_for_ibi,
                    max_read_length,
                    max_write_length,
                    features,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]
        return (status == "I3C_TARGET_SET_CONF_SUCCESS", status)
    
    def write_memory(self, subaddress: [], buffer: list):
        """
        Writes the memory the Supernova as an I3C target represents via USB.

        Args:
        subaddress (list): Register address from which we want to start reading.
        buffer (list): data we want to write

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is the error if the operation failed or None if it was successful
        """
        
        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetWriteMemory(
                    id,
                    subaddress,
                    buffer,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]

        return((True, None) if (status == "I3C_TARGET_WRITE_MEM_SUCCESS") else (False, responses[0]["error"]))
        
    def read_memory(self, subaddress: [], length):
        """
        Reads the memory the Supernova as an I3C target represents via USB.

        Args:
        subaddress (list): Register address from which we want to start reading.
        length (int): data length we want to read, in bytes 

        Returns:
        tuple: A tuple containing two elements:
            - The first element is a Boolean indicating the success (True) or failure (False) of the operation.
            - The second element is either the error if the operation failed or the data if it was successful
        """

        try:
            responses = self.controller.sync_submit([
                lambda id: self.driver.i3cTargetReadMemory(
                    id,
                    subaddress,
                    length,
                )
            ])
        except Exception as e:
            raise BackendError(original_exception=e) from e

        status = responses[0]["result"]

        return((True, responses[0]["data"]) if (status == "I3C_TARGET_READ_MEM_SUCCESS") else (False, responses[0]["error"]))
        
    def wait_for_notification(self, timeout):
        """
        Waits for I3C target notification.

        This method waits for a notification related to I3C target mode for the specified timeout duration.
        It uses the I3C notification subscription to wait for incoming data notifications.

        Args:
        timeout: The duration in seconds to wait for the notification.

        Returns: dictionary that indicates the type of notification (write or read), memory address,
                 transfer length, data and result of the transfer notified.

        """

        # Wait for an I3C notification 
        # with the specified timeout
        data_has_been_received, notification =  self.i3c_notification.wait_for_notification(timeout)

        # Check if the notification was received within the timeout
        if not data_has_been_received:
            return (data_has_been_received, "Timeout occurred while waiting for the I3C Target notification")

        keys_to_remove = {"id", "command", "name", "target_address"}
        new_dict = {key: notification[key] for key in notification if key not in keys_to_remove}

        # Return the received payload if the notification is correct
        return (data_has_been_received, new_dict)    
    