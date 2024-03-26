from supernovacontroller.sequential import SupernovaDevice
from threading import Event

counter = 0
last_ibi = Event()

def main():
    device = SupernovaDevice()

    info = device.open()

    i3c = device.create_interface("i3c.controller")

    i3c.set_parameters(i3c.I3cPushPullTransferRate.PUSH_PULL_12_5_MHZ, i3c.I3cOpenDrainTransferRate.OPEN_DRAIN_4_17_MHZ)
    (success, _) = i3c.init_bus(3300)

    if not success:
        print("I couldn't initialize the bus. Are you sure there's any target connected?")
        exit(1)

    # Target PID in hexadecimal format
    target_pid = [0x6A, 0x04, 0x00, 0x00, 0x00, 0x00]

    # IMPORTANT: Remove the following line when the SupernovaSDK is updated to return a list of numbers
    target_pid = [f"0x{num:02x}" for num in target_pid]

    (deviceFound, icm_device) = i3c.find_target_device_by_pid(target_pid)

    if deviceFound is False:
        print("ICM device not found in the I3C bus")

    print(icm_device)

    target_address = icm_device["dynamic_address"]

    # ---
    # IBI configuration
    # ---

    def is_icm_ibi(name, message):
        source_address = message["header"]["address"]
        return name == "icm_ibi" and source_address == target_address

    def handle_icm_ibi(name, message):
        global counter
        global last_ibi

        payload = message["payload"]
        print(payload)

        counter += 1
        if counter == 10:
            last_ibi.set()

    device.on_notification(name="icm_ibi", filter_func=is_icm_ibi, handler_func=handle_icm_ibi)

    i3c.toggle_ibi(target_address, False)

    # Setup IBIs on IMC device
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x76], [0x00])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x4E], [0x20])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x13], [0x05])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x16], [0x40])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x5F], [0x61])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x60], [0x0F, 0x00])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x50], [0x0E])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x76], [0x01])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x03], [0x38])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x7A], [0x02])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x7C], [0x1F])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x76], [0x04])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x4F], [0x04])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x76], [0x00])
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [0x4E], [0x02])

    i3c.toggle_ibi(target_address, True)

    last_ibi.wait()

    device.close()


if __name__ == "__main__":
    main()