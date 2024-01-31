from supernovacontroller.sequential import SupernovaDevice
import time

def imu_response_format(response):
    if response['header']['hasData']:
        return response['data']

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
    target_pid = [0x00, 0x00, 0x00, 0x00, 0x6A, 0x04]

    # IMPORTANT: Remove the following line when the SupernovaSDK is updated to return a list of numbers
    target_pid = [f"0x{num:02x}" for num in target_pid]

    (deviceFound, icm_device) = i3c.find_target_device_by_pid(target_pid)

    if deviceFound is False:
        print("ICM device not found in the I3C bus")

    print(icm_device)

    target_address = icm_device["dynamic_address"]

    # Check Who I Am Register for ICMM42605
    (_, who_am_i ) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [0x75], 1)
    print("Who Am I Register: ", who_am_i)

    # Define sensor resolutions
    Ascale = 0x03 # 2g full scale
    Gscale = 0x03 # 250 dps full scale
    aRes = 2.0 / 32768.0 # 2 g full scale
    gRes = 250.0 / 32768.0 # 250 dps full scale
    AODR = 0x06 #AODR_1000Hz
    GODR = 0x06 #GODR_1000Hz

    # Initialize Sensor

    # Enable gyro and accel in low noise mode
    ICM42605_PWR_MGMT0 = 0x4E
    (_, power_management_register) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_PWR_MGMT0], 1)
    print("Power Management Register: ", power_management_register)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_PWR_MGMT0], [power_management_register[0] | 0x0F])
    print("Power Management Register written.")
    # Gyro full scale and data rate
    ICM42605_GYRO_CONFIG0 = 0x4F
    (_, gyro_config_register0) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_GYRO_CONFIG0], 1)
    print("Gyro Config Register: ", gyro_config_register0)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_GYRO_CONFIG0], [gyro_config_register0[0] | GODR | Gscale << 5])
    print("Gyro Config Register written.")

    # Set accel full scale and data rate
    ICM42605_ACCEL_CONFIG0 = 0x50
    (_, accel_config) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_ACCEL_CONFIG0], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_ACCEL_CONFIG0], [accel_config[0] | AODR | Ascale << 5])

    # Set temperature sensor low pass filter to 5Hz, use first order gyro filter
    ICM42605_GYRO_CONFIG1 = 0x56
    (_, gyro_config_register1) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_GYRO_CONFIG1], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_GYRO_CONFIG1], [gyro_config_register1[0] | 0xD0])

    # Set both interrupts active high, push-pull, pulsed
    ICM42605_INT_CONFIG0 = 0x63
    (_, int_config0) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_CONFIG0], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_CONFIG0], [int_config0[0] | 0x18 | 0x03])

    # Set bit 4 to zero for proper function of INT1 and INT2
    ICM42605_INT_CONFIG1 = 0x64
    (_, int_config1) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_CONFIG1], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_CONFIG1], [int_config1[0] & ~(0x10)])

    # Route data ready interrupt to INT1
    ICM42605_INT_SOURCE0 = 0x65
    (_, int_source0) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_SOURCE0], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_SOURCE0], [int_source0[0] | 0x08])

    # Route AGC interrupt interrupt to INT2
    ICM42605_INT_SOURCE3 = 0x68
    (_, int_source3) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_SOURCE3], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_SOURCE3], [int_source3[0] | 0x01])

    # Select Bank 4
    ICM42605_REG_BANK_SEL = 0x76
    (_, reg_bank_sel) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_REG_BANK_SEL], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_REG_BANK_SEL], [reg_bank_sel[0] | 0x04])

    # Select unitary mounting matrix
    ICM42605_APEX_CONFIG5 = 0x7A
    (_, apex_config5) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_APEX_CONFIG5], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_APEX_CONFIG5], [apex_config5[0] & ~(0x07)])

    # Select Bank 0
    ICM42605_REG_BANK_SEL = 0x76
    (_, reg_bank_sel) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_REG_BANK_SEL], 1)
    i3c.write(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_REG_BANK_SEL], [reg_bank_sel[0] & ~(0x07)])

    ## Read Status
    ICM42605_INT_STATUS = 0x19
    (_, int_status) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_INT_STATUS], 1)
    print("Status Register: ", int_status)


    # Read data from IMU
    ICM42605_TEMP_DATA1 = 0x1D
    import ctypes

    def readIMUData():
        (_, raw_data) = i3c.read(target_address, i3c.TransferMode.I3C_SDR, [ICM42605_TEMP_DATA1], 14)
        imuData = [0,0,0,0,0,0,0]
        imuData[0] = ctypes.c_int16((raw_data[0] << 8) | raw_data[1]).value
        imuData[1] = ctypes.c_int16((raw_data[2] << 8) | raw_data[3]).value 
        imuData[2] = ctypes.c_int16((raw_data[4] << 8) | raw_data[5]).value
        imuData[3] = ctypes.c_int16((raw_data[6] << 8) | raw_data[7]).value
        imuData[4] = ctypes.c_int16((raw_data[8] << 8) | raw_data[9]).value
        imuData[5] = ctypes.c_int16((raw_data[10] << 8) | raw_data[11]).value
        imuData[6] = ctypes.c_int16((raw_data[12] << 8) | raw_data[13] ).value
        return imuData
    
    # Calibrate IMU
    sum_values = [0, 0, 0, 0, 0, 0, 0]
    accelBias = [0, 0, 0]
    gyroBias = [0, 0, 0]

    for i in range(128):
        # Read data
        imuData = readIMUData()
        sum_values[1] += imuData[1]
        sum_values[2] += imuData[2]
        sum_values[3] += imuData[3]
        sum_values[4] += imuData[4]
        sum_values[5] += imuData[5]
        sum_values[6] += imuData[6]

    accelBias[0] = sum_values[1] * aRes / 128.0
    accelBias[1] = sum_values[2] * aRes / 128.0
    accelBias[2] = sum_values[3] * aRes / 128.0
    gyroBias[0] = sum_values[4] * gRes / 128.0
    gyroBias[1] = sum_values[5] * gRes / 128.0
    gyroBias[2] = sum_values[6] * gRes / 128.0

    if accelBias[0] > 0.8:
        accelBias[0] -= 1.0  # Remove gravity from the x-axis accelerometer bias calculation
    if accelBias[0] < -0.8:
        accelBias[0] += 1.0  # Remove gravity from the x-axis accelerometer bias calculation
    if accelBias[1] > 0.8:
        accelBias[1] -= 1.0  # Remove gravity from the y-axis accelerometer bias calculation
    if accelBias[1] < -0.8:
        accelBias[1] += 1.0  # Remove gravity from the y-axis accelerometer bias calculation
    if accelBias[2] > 0.8:
        accelBias[2] -= 1.0  # Remove gravity from the z-axis accelerometer bias calculation
    if accelBias[2] < -0.8:
        accelBias[2] += 1.0  # Remove gravity from the z-axis accelerometer bias calculation 

    start_time = time.time()

    accel_data = []
    gyro_data = []
    # Read and plot IMU Data for 30 seconds
    while True and time.time() < start_time + 30:
        # Read data
        imuData = readIMUData()

        ax = imuData[1]*aRes - accelBias[0]
        ay = imuData[2]*aRes - accelBias[1]  
        az = imuData[3]*aRes - accelBias[2]
        accel_data.append([ax, ay, az])

        # Calculate the gyro value into actual degrees per second
        gx = imuData[4]*gRes - gyroBias[0] 
        gy = imuData[5]*gRes - gyroBias[0]
        gz = imuData[6]*gRes - gyroBias[0]
        gyro_data.append([gx, gy, gz])

    print("Acceleration data:")
    print(accel_data)
    print("Gyroscope data:")
    print(gyro_data)

if __name__ == "__main__":
    main()