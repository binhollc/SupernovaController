from supernovacontroller.sequential import SupernovaDevice
from BinhoSupernova.commands.definitions import I3cTargetMemoryLayout_t
from BinhoSupernova.commands.definitions import I3cOffline
from BinhoSupernova.commands.definitions import PartNOrandom
from BinhoSupernova.commands.definitions import DdrOk
from BinhoSupernova.commands.definitions import IgnoreTE0TE1Errors
from BinhoSupernova.commands.definitions import MatchStartStop
from BinhoSupernova.commands.definitions import AlwaysNack

def main():
    """
    Basic example to illustrate I3C target mode usage with SupernovaController.
    With two Supernovas connected between them via the HV bus, one is initalized as an I3C controller and the other
    one as an I3C target. The target acts as a memory with different layouts:
    - 256 registers of 4 byte size
    - 1024 registers of 1 bytes size
    
    Sequence of commands:
    - Initialize the Devices and create its interfaces: 
      Create and open a connection to the Supernova host adapter for both the I3C controller and the I3C target.
      Create an I3C interface for communication with both the I3C controller and the I3C target.
    - Initialize the I3C peripherals: 
      Init the peripheral of one Supernova as an I3C controller and the other one as an I3C target with a memory layout of 
      1024 registers of 1 byte size.
    - Set I3C Parameters and initialize the Bus: Set transfer rates and initialize the I3C bus with a specific voltage level.
    - Discover Targets on I3C Bus: Fetch a list of devices present on the I3C bus.
    - Set the target configuration: Configure the target Supernova.
    - Perform CCC (Common Command Code) Transfers: Send various CCC commands to the target device to get or set parameters.
    - Write and read the target memory via USB
    - Write/Read Transfers: Demonstrate write and read operations over the I3C bus and handling of border cases.
    - Initialize the I3C target peripheral: 
      Re-Init the peripheral of the target Supernova with a memory layout of 256 registers of 4 bytes size.
    - Initialize the Bus: Initialize the I3C bus again since the target Supernova was re-initialized.
    - Configure the target configuration: Configures the target Supernova.
    - Perform CCC (Common Command Code) Transfers: Send various CCC commands to the target device to get or set parameters.
    - Write and read the target memory via USB
    - Write/Read Transfers: Demonstrate write and read operations over the I3C bus and handling of border cases.
    - Close Device Connection: Close the connection to the Supernova devices.
    """

    print("-----------------------")
    print("Initialize Supernovas")
    print("-----------------------")

    
    devices = SupernovaDevice.openAllConnectedSupernovaDevices()
    target_device = devices[0]
    i3c_target = target_device.create_interface("i3c.target")
    controller_device = devices[1]
    i3c_controller = controller_device.create_interface("i3c.controller")

    print("--------------------------------------------------------------------------------------------------------")
    print("Initialize controller peripheral and target peripheral as a memory of 1024 registers of 1 byte size")
    print("--------------------------------------------------------------------------------------------------------")

    MEMORY_LAYOUT               = I3cTargetMemoryLayout_t.MEM_1_BYTE
    USECONDS_TO_WAIT_FOR_IBI    = 0x69
    MRL                         = 0x100
    MWL                         = 0x100
    TARGET_CONF                 = I3cOffline.OFFLINE_UNFIT.value |  \
                                  PartNOrandom.PART_NUMB_DEFINED.value |  \
                                  DdrOk.ALLOWED_DDR.value |  \
                                  IgnoreTE0TE1Errors.IGNORE_ERRORS.value |  \
                                  MatchStartStop.NOT_MATCH.value |  \
                                  AlwaysNack.NOT_ALWAYS_NACK.value    
    
    success, status = i3c_target.target_init(MEMORY_LAYOUT, USECONDS_TO_WAIT_FOR_IBI, MRL, MWL, TARGET_CONF)
    print("Target initialized correctly" if success else "Could not initialize the target")

    success, status = i3c_controller.controller_init()
    print("Controller initialized correctly" if success else "Could not initialize the controller")

    print("--------------------")
    print("Bus initialization")
    print("--------------------")

    i3c_controller.set_parameters(i3c_controller.I3cPushPullTransferRate.PUSH_PULL_5_MHZ, i3c_controller.I3cOpenDrainTransferRate.OPEN_DRAIN_1_25_MHZ)
    (success, _) = i3c_controller.init_bus(3300)
    if success:
        print("Bus successfully initialized")
    else:
        print("Bus initialization fail. Make sure that there is at least one target connected")
        exit(1)

    (_, targets) = i3c_controller.targets()
    
    target_address = targets[0]["dynamic_address"]

    print("--------------------")
    print("CCC transfers")
    print("--------------------")

    (_, result) = i3c_controller.ccc_getpid(target_address)
    print(f"PID: {result}")
    (_, result) = i3c_controller.ccc_getbcr(target_address)
    print(f"BCR: {result}")
    (_, result) = i3c_controller.ccc_getdcr(target_address)    
    print(f"DCR: {result}")
    (_, result) = i3c_controller.ccc_getmwl(target_address)
    print(f"MWL: {result}")
    MWL = 1024
    i3c_controller.ccc_unicast_setmwl(target_address, MWL)
    (_, result) = i3c_controller.ccc_getmwl(target_address)
    print(f"MWL: {result}")
    (_, result) = i3c_controller.ccc_getmrl(target_address)
    print(f"MRL: {result}")
    MRL = 512
    i3c_controller.ccc_unicast_setmrl(target_address, MRL)
    (_, result) = i3c_controller.ccc_getmrl(target_address)
    print(f"MRL: {result}")
    (_, data) = i3c_controller.ccc_unicast_get_status(target_address)
    print(f"STATUS: {data}")
    (success, _) = i3c_controller.toggle_ibi(target_address, True)
    print("Successfully performed an ENEC" if success else "ENEC failed")
    (success, _) = i3c_controller.toggle_ibi(target_address, False)
    print("Successfully performed a DISEC" if success else "DISEC failed")
    new_target_address = 0x0A    
    (_, data) = i3c_controller.ccc_setnewda(target_address, new_target_address)
    if success is True:
        print(f"Successfully set new dynamic address")
        target_address = new_target_address
    else:
        print(f"Could not set new dynamic address") 

    print("--------------------------------")
    print("I3C_TARGET_SET_CONFIGURATION")
    print("--------------------------------")

    USECONDS_TO_WAIT_FOR_IBI    = 0x69
    MRL                         = 0x300
    MWL                         = 0x250
    TARGET_CONF                 = I3cOffline.OFFLINE_UNFIT.value |  \
                                  PartNOrandom.PART_NUMB_DEFINED.value |  \
                                  DdrOk.ALLOWED_DDR.value |  \
                                  IgnoreTE0TE1Errors.IGNORE_ERRORS.value |  \
                                  MatchStartStop.NOT_MATCH.value |  \
                                  AlwaysNack.NOT_ALWAYS_NACK.value   
    success, status = i3c_target.set_configuration(USECONDS_TO_WAIT_FOR_IBI, MRL, MWL, TARGET_CONF)
    print("Configuration set correctly" if success else "Could not configure the target")

    (_, result) = i3c_controller.ccc_getmrl(target_address)
    print(f"MRL with new configuration: {result}")
    (_, result) = i3c_controller.ccc_getmwl(target_address)
    print(f"MWL with new configuration: {result}")

    print("-------------------------------------------------------")
    print("I3C_TARGET_WRITE_MEMORY and I3C_TARGET_READ_MEMORY")
    print("-------------------------------------------------------")

    SUBADDR = 0x0000
    DATA = [i%0xFA for i in range(0,1024)]
    LENGTH = 100
    (success, error) = i3c_target.write_memory(SUBADDR, DATA)
    print("Memory was written successfully" if success else f"Could not write the memory, error: {error}")

    (success, data) = i3c_target.read_memory(SUBADDR, LENGTH)
    print(f"Successfully read data: {data}" if success else f"An error arose while reading memory: {data}")

    print("--------------------")
    print("Write/Read transfers")
    print("--------------------")

    # I3C WRITE INDICATING START REGISTER ADDRESS AND DATA
    SUBADDR     = [0x00, 0x00]
    DATA        = [0xEE for i in range(5)]
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # I3C READ WITHOUT INDICATING START REGISTER ADDRESS
    SUBADDR     = []
    LENGTH      = 10
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # I3C READ INDICATING START REGISTER ADDRESS
    # (A WRITE FOLLOWED BY A READ WITH A RS IN BETWEEN)
    SUBADDR     = [0xBC, 0x02] # 700
    LENGTH      = 5 # in bytes
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # I3C WRITE INDICATING THE START ADDRESS FOLLOWED BY A READ WITHOUT ADDRESS
    SUBADDR     = [0xF4, 0x03] # 1012
    DATA        = []
    LENGTH      = 6
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, [], LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # BORDER CASE: USER TRIES TO START A TRANSFER SURPASSING THE MEMORY RANGE
    # THE TARGET WILL IGNORE THE BYTES OF ADDRESS AND WILL START THE TRANSFER FROM THE END OF THE PREVIOUS ONE
    SUBADDR     = [0x01, 0x04] # 1025
    DATA        = [0xEE for i in range(4)]
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # BORDER CASE: THE TRANSFER STARTS IN AN ALLOWED ADDRESS BUT TRIES TO SURPASS THE MEMORY RANGE ON THE GO
    # ONLY THE BYTES IN THE ALLOWED RANGE ARE MODIFIED, THE REST ARE DISCARDED
    SUBADDR     = [0xFC, 0x03] # 1020
    DATA        = []
    LENGTH      = 30
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, [], LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)
    
    print("-------------------------------------------------------------------------------")
    print("Initialize target peripheral as a memory of 256 registers of 4 byte size")
    print("-------------------------------------------------------------------------------")

    MEMORY_LAYOUT               = I3cTargetMemoryLayout_t.MEM_4_BYTES
    USECONDS_TO_WAIT_FOR_IBI    = 0x69
    MRL                         = 0x300
    MWL                         = 0x250
    TARGET_CONF                 = I3cOffline.OFFLINE_UNFIT.value |  \
                                  PartNOrandom.PART_NUMB_DEFINED.value |  \
                                  DdrOk.ALLOWED_DDR.value |  \
                                  IgnoreTE0TE1Errors.IGNORE_ERRORS.value |  \
                                  MatchStartStop.NOT_MATCH.value |  \
                                  AlwaysNack.NOT_ALWAYS_NACK.value    
    
    success, status = i3c_target.target_init(MEMORY_LAYOUT, USECONDS_TO_WAIT_FOR_IBI, MRL, MWL, TARGET_CONF)
    print("Target initialized correctly" if success else "Could not initialize the target")

    print("--------------------")
    print("Bus initialization")
    print("--------------------")

    (success, _) = i3c_controller.init_bus(3300)
    if success:
        print("Bus successfully initialized")
    else:
        print("Bus initialization fail. Make sure that there is at least one target connected")
        exit(1)
        
    (_, targets) = i3c_controller.targets()    
    target_address = targets[0]["dynamic_address"]
    
    print("-------------------------------------------------------")
    print("I3C_TARGET_WRITE_MEMORY and I3C_TARGET_READ_MEMORY")
    print("-------------------------------------------------------")

    SUBADDR_0 = 0x00
    SUBADDR_1 = 0x0A
    DATA_0 = [i%0xFA for i in range(0,1024)]
    DATA_1 = [0xFF for i in range(0,8)]
    LENGTH = 100
    (success, error) = i3c_target.write_memory(SUBADDR_0, DATA_0)
    print("Memory was written successfully" if success else f"Could not write the memory, error: {error}")

    (success, error) = i3c_target.write_memory(SUBADDR_1, DATA_1)
    print("Memory was written successfully" if success else f"Could not write the memory, error: {error}")

    (success, data) = i3c_target.read_memory(SUBADDR_0, LENGTH)
    print(f"Successfully read data: {data}" if success else f"An error arose while reading memory: {data}")
    
    print("--------------------")
    print("Write/Read transfers")
    print("--------------------")

    # I3C WRITE INDICATING START REGISTER ADDRESS AND DATA
    SUBADDR     = [0x3B] # register 59 = byte 236
    DATA        = [0xEE for i in range(8)]
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)

    # I3C READ WITHOUT INDICATING START REGISTER ADDRESS
    SUBADDR     = []
    LENGTH      = 4 # in bytes
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # I3C READ INDICATING START REGISTER ADDRESS
    # (A WRITE FOLLOWED BY A READ WITH A RS IN BETWEEN)
    SUBADDR     = [0x7D] # register 125 = byte 500
    LENGTH      = 8 # in bytes
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # I3C WRITE INDICATING THE START ADDRESS FOLLOWED BY A READ WITHOUT ADDRESS
    SUBADDR     = [0xFE] # register 254 = byte 1016  
    DATA        = []
    LENGTH      = 4 # in bytes
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, [], LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    # BORDER CASE: THE TRANSFER STARTS IN AN ALLOWED ADDRESS BUT TRIES TO SURPASS THE MEMORY RANGE ON THE GO
    # ONLY THE BYTES IN THE ALLOWED RANGE ARE MODIFIED, THE REST ARE DISCARDED
    SUBADDR     = [0xFD] # register 253 = byte 1012
    DATA        = []
    LENGTH      = 40 # in bytes
    result = i3c_controller.write(target_address, i3c_controller.TransferMode.I3C_SDR, SUBADDR, DATA)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)
    result = i3c_controller.read(target_address, i3c_controller.TransferMode.I3C_SDR, [], LENGTH)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)
    notification_flag, notification_message = i3c_target.wait_for_notification(1)
    print(notification_message)

    print("-------------------------------------------------------")
    print("CLOSE CONNECTION TO SUPERNOVAS")
    print("-------------------------------------------------------")

    controller_device.close()
    target_device.close()

if __name__ == "__main__":
    main()