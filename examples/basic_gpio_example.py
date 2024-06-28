from supernovacontroller.sequential import SupernovaDevice
from BinhoSupernova.commands.definitions import (
    GpioPinNumber, GpioLogicLevel, GpioFunctionality, GpioTriggerType
)
from threading import Event
gpio_interrupt_event = Event()

def main():
    """
    Basic example to illustrate GPIO usage with SupernovaController.

    In this example we initialize GPIO pins with the following configurations:
        GPIO_6: Digital Output
        GPIO_5: Digital Input with Interrupts for both rising and falling edges
        This example assumes pin 5 and pin 6 are short-circuited.

    The script performs the following steps:
        1. Configures GPIO_6 as a Digital Output.
        2. Configures GPIO_5 as a Digital Input.
        3. Sets GPIO_6 to HIGH and reads the value from GPIO_5.
        4. Sets GPIO_6 to LOW and reads the value from GPIO_5.
        5. Configures an interrupt on GPIO_5 for both rising and falling edges.
        6. Toggles GPIO_6 to generate 4 interrupts on GPIO_5.
        7. Disables the interrupt on GPIO_5.
    """
    device = SupernovaDevice()

    print("Opening Supernova host adapter device and getting access to the GPIO interface...")
    info = device.open()
    gpio = device.create_interface("gpio")

    # Important note about GPIO voltage set depending on hardware revision:
    # - If Rev. B is used, voltage can be set in pins 1 and 2 with setI3cBusVoltage(). Pins 3 to 6 are fixed at 3.3 V.
    # - If Rev. C is used, voltage is set with setI2cSpiUartBusVoltage() for all pins.
    print("Initializing GPIO peripheral.")
    (success, _) = gpio.set_pins_voltage(3300)
    if not success:
        print("Couldn't set the GPIO pins voltage.")
        exit(1)

    print("Configuring GPIO pins...")
    (success, _) = gpio.configure_pin(GpioPinNumber.GPIO_6, GpioFunctionality.DIGITAL_OUTPUT)
    if not success:
        print("Couldn't configure GPIO_6 as Digital Output.")
        exit(1)

    (success, _) = gpio.configure_pin(GpioPinNumber.GPIO_5, GpioFunctionality.DIGITAL_INPUT)
    if not success:
        print("Couldn't configure GPIO_5 as Digital Input.")
        exit(1)

    print("Setting GPIO_6 to HIGH and reading value from GPIO_5...")
    (success, _) = gpio.digital_write(GpioPinNumber.GPIO_6, GpioLogicLevel.HIGH)
    if not success:
        print("Couldn't set GPIO_6 to HIGH.")
        exit(1)

    (success, value) = gpio.digital_read(GpioPinNumber.GPIO_5)
    if success:
        print(f"GPIO_5 read value: {value}")
    else:
        print("Failed to read GPIO_5 value.")

    print("Setting GPIO_6 to LOW and reading value from GPIO_5...")
    (success, _) = gpio.digital_write(GpioPinNumber.GPIO_6, GpioLogicLevel.LOW)
    if not success:
        print("Couldn't set GPIO_6 to LOW.")
        exit(1)

    (success, value) = gpio.digital_read(GpioPinNumber.GPIO_5)
    if success:
        print(f"GPIO_5 read value: {value}")
    else:
        print("Failed to read GPIO_5 value.")

    # -- Interruptions
    # To manage GPIO notifications, we have to pass to the on_notification() method the following functions:
    # - Filter function: it checks if the notification is a GPIO interrupt.
    # - Handler function: it processes the interruption. In our case prints relevant data and sets the event.
    def is_gpio_interrupt(name, message):
        return message['name'].strip() == "GPIO INTERRUPTION"
    
    def handle_gpio_interrupt(name, message):
        print(f"GPIO interrupt notification on pin: {message['pin_number']}")
        gpio_interrupt_event.set()

    print("Registering GPIO interrupt handlers...")
    device.on_notification(name="GPIO INTERRUPTION", filter_func=is_gpio_interrupt, handler_func=handle_gpio_interrupt) # gpio-interruption

    print("Configuring interrupt on GPIO_5 for both rising and falling edges...")
    (success, _) = gpio.set_interrupt(GpioPinNumber.GPIO_5, GpioTriggerType.TRIGGER_BOTH_EDGES)
    if not success:
        print("Couldn't set interrupt on GPIO_5.")
        exit(1)

    # Since pin 6 was in LOW, the following loop will generate 4 interruptions because
    # we have set the interruption trigger type to check both edges (rising and falling)
    print("Toggling GPIO_6 to generate interrupts on GPIO_5...")
    for level in [GpioLogicLevel.HIGH, GpioLogicLevel.LOW, GpioLogicLevel.HIGH, GpioLogicLevel.LOW]:
        (success, _) = gpio.digital_write(GpioPinNumber.GPIO_6, level)
        if not success:
            print(f"Couldn't set GPIO_6 to {level}.")
            exit(1)
        # Wait for the GPIO interrupt to be processed
        gpio_interrupt_event.wait()
        gpio_interrupt_event.clear()

    print("Disabling interrupt on GPIO_5...")
    (success, _) = gpio.disable_interrupt(GpioPinNumber.GPIO_5)
    if not success:
        print("Couldn't disable interrupt on GPIO_5.")
        exit(1)

    print("Closing Supernova device connection...")
    device.close()

if __name__ == "__main__":
    main()
