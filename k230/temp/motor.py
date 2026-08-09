"""K230 UART1 stepper-motor controller.

The motor controller is connected to K230 IO9 (UART1 TX) at 115200 baud.
Command format: @<motor_id>#<control_type><data>$
"""

from machine import FPIOA, UART


BAUDRATE = 115200
UART_TX_PIN = 9

uart1 = None
_owns_uart = False


def set_uart(uart):
    """Use an existing UART-compatible object (for example AppManager.uart)."""
    global uart1, _owns_uart
    uart1 = uart
    _owns_uart = False


def init_uart():
    """Create UART1 on IO9 only when no shared UART was supplied."""
    global uart1, _owns_uart
    if uart1 is None:
        fpioa = FPIOA()
        fpioa.set_function(UART_TX_PIN, FPIOA.UART1_TXD, ie=0, oe=1, pu=1)
        uart1 = UART(UART.UART1, BAUDRATE)
        _owns_uart = True
    return uart1


def _validate_motor_id(motor_id):
    """Return a validated motor ID in the range 0..9."""
    if not isinstance(motor_id, int) or isinstance(motor_id, bool):
        raise ValueError("motor_id must be an integer from 0 to 9")
    if motor_id < 0 or motor_id > 9:
        raise ValueError("motor_id must be from 0 to 9")
    return motor_id


def send_command(motor_id, control_type, data=""):
    """Send one motor command and return True when UART write succeeds."""
    _validate_motor_id(motor_id)
    if control_type not in ("P", "R", "B", "A", "D", "C", "Z", "E"):
        raise ValueError("unsupported motor control type")

    command = "@{}#{}{}$".format(motor_id, control_type, data)
    try:
        init_uart().write(command.encode("ascii"))
        return True
    except Exception as exc:
        print("motor command send failed:", exc)
        return False


def set_motor(motor_id):
    """Send the protocol's raw motor-selection command: *<motor_id>."""
    _validate_motor_id(motor_id)
    command = "*{}".format(motor_id)
    try:
        init_uart().write(command.encode("ascii"))
        return True
    except Exception as exc:
        print("motor selection send failed:", exc)
        return False


def turn_off_motor(motor_id):
    """Turn off a motor (P)."""
    return send_command(motor_id, "P")


def turn_on_motor(motor_id):
    """Turn on a motor (R)."""
    return send_command(motor_id, "R")


def go_to_home(motor_id):
    """Move a motor to its home position (B)."""
    return send_command(motor_id, "B")


def set_absolute_angle(motor_id, angle):
    """Set an absolute angle (A); positive and negative values are accepted."""
    sign = "+" if angle >= 0 else "-"
    return send_command(motor_id, "A", "{}{}".format(sign, abs(angle)))


def set_incremental_angle(motor_id, angle):
    """Move by an angle increment (D)."""
    sign = "+" if angle >= 0 else "-"
    return send_command(motor_id, "D", "{}{}".format(sign, abs(angle)))


def set_speed(motor_id, speed):
    """Set motor speed (C) in the inclusive range -1000..1000."""
    if speed < -1000 or speed > 1000:
        print("speed must be from -1000 to 1000")
        return False
    sign = "+" if speed >= 0 else "-"
    return send_command(motor_id, "C", "{}{}".format(sign, abs(speed)))


def set_zero_position(motor_id):
    """Store the current position as zero (Z); power-cycle to apply it."""
    return send_command(motor_id, "Z")


def clear_overcurrent(motor_id):
    """Clear a motor overcurrent state (E)."""
    return send_command(motor_id, "E")


def deinit():
    """Release UART1 when motor control is no longer needed."""
    global uart1, _owns_uart
    if uart1 is not None and _owns_uart:
        uart1.deinit()
    uart1 = None
    _owns_uart = False
