# GPIO_ID = GPIO_port * 8 + GPIO_pin + GPIO_based_number.
 
# 1) cd /sys/class/gpio
# 2) echo <pin_number>  > export
# eg echo 462 > export
# 3) cd <pin_directory>
# 4) echo out >direction
# 5) echo 1/0 > value ( toggle 1 /0 )
 
# P5_6 -->  462 ( J2 header pin number 1 )
# P5_7 -->  463 ( J2 header pin number 2 )

import os
import time

GPIO_ROOT = '/sys/class/gpio'
GPIO_EXPORT = os.path.join(GPIO_ROOT, 'export')
GPIO_UNEXPORT = os.path.join(GPIO_ROOT, 'unexport')
GPIO_BASE_NUMBER = 416

FMODE = 'w+'  # w+ overwrites and truncates existing files
IN, OUT = 'in', 'out'
LOW, HIGH = 0, 1


class GPIOPin:

    def __init__(self, port, pin, direction, initial=LOW, active_low=LOW):
        self.pin_number = (port*8) + pin + GPIO_BASE_NUMBER
        if port == 10:
            port = 'A'
        elif port == 11:
            port = 'B'
        else:
            port = str(port)

        self.folder_name = 'P' + port + '_' + str(pin)

        if not os.path.exists(os.path.join(GPIO_ROOT, self.folder_name)):
            with open(GPIO_EXPORT, FMODE) as f:
                f.write(str(self.pin_number))
                f.flush()

        with open(os.path.join(GPIO_ROOT, self.folder_name, 'direction'), FMODE) as f:
            f.write(direction)
            f.flush()

        if direction == 'out':

            with open(os.path.join(GPIO_ROOT, self.folder_name, 'active_low'), FMODE) as f:
                f.write('1' if active_low else '0')
                f.flush()            

            with open(os.path.join(GPIO_ROOT, self.folder_name, 'value'), FMODE) as f:
                f.write('1' if initial else '0')
                f.flush()  

        # Using unbuffered binary IO is ~ 3x faster than text
        self.value = open(os.path.join(GPIO_ROOT, self.folder_name, 'value'), 'wb+', buffering=0)

    def read(self):
        self.value.seek(0)
        value = self.value.read()
        try:
            return value[0] - 48
        except TypeError:
            return int(value)

    def write(self, value):
        self.value.write(b'1' if value else b'0')

    def cleanup(self):
        self.value.close()

        if not os.path.exists(os.path.join(GPIO_ROOT, self.folder_name)):
            with open(GPIO_UNEXPORT, FMODE) as f:
                f.write(str(self.pin_number))
                f.flush()

