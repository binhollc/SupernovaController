from supernovacontroller.sequential import SupernovaDevice

def main():
    """
    Basic example to illustrate i3c protocol usage with SupernovaController.
    
    Sequence of commands:
    - Initialize the Device: Creates and opens a connection to Supernova host adapter.
    - Create I3C Interface: Creates an I3C interface for communication.
    - Set I3C Parameters and Initialize Bus: Sets transfer rates and initializes the I3C bus with a specific voltage level.
    - Discover Targets on I3C Bus: Fetches a list of devices present on the I3C bus.
    - Find Specific ICM Device: Uses find_target_device_by_pid to find a specific device based on its PID.
    - Perform CCC (Common Command Code) Transfers: Sends various CCC commands to the target device to get or set parameters.
    - Write/Read Transfers: Demonstrates write and read operations over the I3C bus.
    - Reset I3C Bus and Targets: Resets the bus and fetches the target list again.
    - Close Device Connection: Closes the connection to the Supernova device.
    """
    device = SupernovaDevice()
    print("Opening Supernova host adapter device and getting access to the I3C protocol interface...")
    info = device.open()
    i3c = device.create_interface("i3c.controller")

    print("Initializing the bus...\n")
    i3c.set_parameters(i3c.I3cPushPullTransferRate.PUSH_PULL_12_5_MHZ, i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_4_17_MHZ)
    (success, _) = i3c.init_bus(3300)
    if not success:
        print("I couldn't initialize the bus. Are you sure there's any target connected?")
        exit(1)

    # Target PID in hexadecimal format
    target_pid = [0x00, 0x00, 0x00, 0x00, 0x6A, 0x04]

    # IMPORTANT: Remove the following line when the SupernovaSDK is updated to return a list of numbers
    target_pid = [f"0x{num:02x}" for num in target_pid]

    (deviceFound, icm_device) = i3c.find_target_device_by_pid(target_pid)

    if deviceFound is False:
        print("ICM device not found in the I3C bus")
        exit(1)

    print(f'Targets in the I3C bus: {icm_device}')

    target_address = icm_device["dynamic_address"]
    print(f'Target address: {target_address} \n')

    print("-------------")
    print("CCC Transfers")
    print("-------------")
    result = i3c.ccc_getpid(target_address)
    print(f'GETPID: {result[1]} \n')
    result = i3c.ccc_getbcr(target_address)
    print(f'GETBCR: {result[1]} \n')
    result = i3c.ccc_getdcr(target_address)
    print(f'GETDCR: {result[1]} \n')
    result = i3c.ccc_getcaps(target_address)
    print(f'GETCAPS (Get Capabilities): {result[1]} \n')
    result = i3c.ccc_getmxds(target_address)
    print(f'GETMXDS (Get Max Data Speed): {result[1]} \n')
    result = i3c.ccc_getmrl(target_address)
    print(f'GETMRL (Get Max Read Length): {result[1]} \n')
    MRL = 256
    result = i3c.ccc_unicast_setmrl(target_address, MRL)
    print(f'UNICAST SETMRL (Set Max Read Length) in: {MRL} \n')
    result = i3c.ccc_getmrl(target_address)
    print(f'GETMRL: {result[1]} \n')
    result = i3c.ccc_getmwl(target_address)
    print(f'GETMWL (Get Max Write Length): {result[1]} \n')
    MWL = 128
    result = i3c.ccc_broadcast_setmwl(MWL)
    print(f'BROADCAST SETMWL (Set Max Write Length) in: {MWL} \n')
    result = i3c.ccc_getmwl(target_address)
    print(f'GETMWL: {result[1]} \n')

    print("--------------------")
    print("Write/Read transfers")
    print("--------------------")
    SUBADR = 0x16
    DATA = [0x40] 
    result = i3c.write(target_address, i3c.TransferMode.I3C_SDR, [SUBADR], DATA)
    print(f'Write {DATA} in subaddress {SUBADR}')
    LENGTH = 1
    result = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [SUBADR], LENGTH)
    print(f'Read from subaddress {SUBADR}: {result[1]}\n')
    DATA = [0xDE, 0xAD, 0xBE, 0xEF] 
    result = i3c.write(target_address, i3c.TransferMode.I3C_SDR, [SUBADR], DATA)
    print(f'Write {DATA} in subaddress {SUBADR}')
    LENGTH = 4
    result = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [SUBADR], LENGTH)
    print(f'Read from subaddress {SUBADR}: {result[1]}\n')

    print("---------")
    print("Reset bus")
    print("---------")
    result = i3c.reset_bus()
    print("Resetting bus...")
    result = i3c.targets()
    print(f'Targets in the I3C bus: {result[1]}')

    device.close()

if __name__ == "__main__":
    main()