##!/usr/bin/env python3
# encoding: utf-8
import time
import serial
from threading import Lock
from gpio import *
from hiwonder_servo_cmd import *

exception = None

rx_pin = GPIOPin(9, 6, 'out', LOW)
#rx_pin = GPIOPin(8, 6, 'out', HIGH)
#high_pin = GPIOPin(7, 2, 'out', HIGH)
tx_pin = GPIOPin(11, 3, 'out', HIGH)
#tx_pin = GPIOPin(8, 7, 'out', LOW)

#reset_pin = GPIOPin(8, 0, 'out', HIGH)

def port_as_write():
    tx_pin.write(1)
    rx_pin.write(0)

def port_as_read():
    tx_pin.write(1)
    rx_pin.write(1)

port_as_write()

class servo_state:
    def __init__(self):
        self.start_timestamp = time.time()
        self.end_timestamp = time.time()
        self.speed = 200
        self.goal = 500
        self.estimated_pos = 500


class HiwonderServoController:
    def __init__(self, port, baudrate):
        """打开串口, 初始化参数(open the serial port. Initialize the parameter)"""
        try:
            self.serial_mutex = Lock()
            self.ser = None
            self.timeout = 10
            self.ser = serial.Serial(port, baudrate, timeout=0.01)
            self.port_name = port
        except SerialOpenError:
            raise SerialOpenError(port, baudrate)

    def __del__(self):
        self.close()

    def close(self):
        """
        Be nice, close the serial port.
        """
        if self.ser:
            self.ser.flushInput()
            self.ser.flushOutput()
            self.ser.close()

    def checksum(self, packet):
        # 计算校验和
        sum = 0x00
        for b in packet:  # 求和
            sum += b
        sum = sum - 0x55 - 0x55  # 去掉命令开头的两个 0x55
        sum = ~sum  # 取反
        return sum & 0xff

    def __write_serial(self, data):
        self.ser.flushInput()
        port_as_write()
        #value = []
        i = 0
        while i < len(data):
            #val = []
            #for k in range(i, i+10):
            value = data[i].to_bytes(1, 'big')
                #val.append(data[k])
                #print(val)
            self.ser.write(value)
            time.sleep(0.00007) 
            i += 1
            #if i%10 == 0:
            #    time.sleep(0.005)

    def __read_response(self, servo_id):
        self.ser.flushInput()
        port_as_read()
        time.sleep(0.005)
        data = []
        try:
            data.extend(self.ser.read(4))
            if not data[0:2] == [0x55, 0x55]:
                raise Exception('Wrong packet prefix' + str(data[0:2]))
            data.extend(self.ser.read(data[3] - 1))
        except Exception as e:
            raise DroppedPacketError('Invalid response received from servo ' + str(servo_id) + ' ' + str(e))
        # finally:
        #    port_as_write()

        # verify checksum
        checksum = 255 - (sum(data[2: -1]) % 256)
        if not checksum == data[-1]:
            raise ChecksumError(servo_id, data, checksum)
        return data

    def read(self, servo_id, cmd):
        # Number of bytes following standard header (0xFF, 0xFF, id, length)
        length = 3  # instruction, address, size, checksum

        ##计算校验和
        checksum = 255 - ((servo_id + length + cmd) % 256)
        # packet: 0x55  0x55  ID LENGTH INSTRUCTION PARAM_1 ... CHECKSUM
        packet = [0x55, 0x55, servo_id, length, cmd, checksum]

        data = []
        with self.serial_mutex:
            for i in range(10):
                try:
                    self.__write_serial(packet)
                    # wait for response packet from the motor
                    # read response
                    data = self.__read_response(servo_id)
                    timestamp = time.time()
                    data.append(timestamp)
                    break
                except Exception as e:
                    if i == 49:
                        raise e
        return data

    def write(self, servo_id, cmd, params):
        """ Write the values from the "data" list to the servo with "servo_id"
        starting with data[0] at "address", continuing through data[n-1] at
        "address" + (n-1), where n = len(data). "address" is an integer between
        0 and 49. It is recommended to use the constants in module dynamixel_const
        for readability. "data" is a list/tuple of integers.
        To set servo with id 1 to position 276, the method should be called
        like:
            write(1, DXL_GOAL_POSITION_L, (20, 1))
        """
        # Number of bytes following standard header (0xFF, 0xFF, id)
        length = 3 + len(params)  # length, cmd, params, checksum
        # Check Sum = ~ ((ID + LENGTH + COMMAND + PARAM_1 + ... + PARAM_N) & 0xFF)
        checksum = 255 - ((servo_id + length + cmd + sum(params)) % 256)
        # packet: FF  FF  ID LENGTH INSTRUCTION PARAM_1 ... CHECKSUM
        packet = [0x55, 0x55, servo_id, length, cmd]
        packet.extend(params)
        packet.append(checksum)
        with self.serial_mutex:
            self.__write_serial(packet)

    def get_servo_position(self, servo_id):
        response = self.read(servo_id, HIWONDER_SERVO_POS_READ)
        if response:
            self.exception_on_error(response[4], servo_id, 'fetching present position')
            return response[5] + (response[6] << 8)

    def get_servo_voltage(self, servo_id):
        response = self.read(servo_id, HIWONDER_SERVO_VIN_READ)
        if response:
            self.exception_on_error(response[4], servo_id, 'fetching supplied voltage')
            return response[5] + (response[6] << 8)

    def set_timeout(self, t=10):
        self.timeout = t

    def set_servo_id(self, oldid, newid):
        '''
        配置舵机id号, 出厂默认为1(configure servo id which is 1 by default)
        :param oldid: 原来的id， 出厂默认为1(param oldid: original id. It is 1 by default)
        :param newid: 新的id(param newid: new id)
        '''
        self.write(oldid, HIWONDER_SERVO_ID_WRITE, (newid,))

    def get_servo_id(self, servo_id=None):
        '''
        读取串口舵机id(read serial bus servo id)
        :param id: 默认为空(param id: none by default)
        :return: 返回舵机id(return servo id)
        '''
        count = 0
        while True:
            count += 1
            response = None
            if servo_id is None:  # 总线上只能有一个舵机(there is only one servo on the bus)
                response = self.read(0xfe, HIWONDER_SERVO_ID_READ)
            else:
                response = self.read(servo_id, HIWONDER_SERVO_ID_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def set_servo_position(self, servo_id, position, duration=None):
        '''
        驱动串口舵机转到指定位置(drive the serial servo to rotate to the designated position)
        :param id: 要驱动的舵机id(param id: the  servo id to be driven)
        :pulse: 位置(pulse: position)
        :use_time: 转动需要的时间(use_time: time taken for rotation)
        '''
        # print("id:{}, pos:{}, duration:{}".format(servo_id, position, duration))

        current_timestamp = time.time()
        if duration is None:
            duration = 20
        duration = 0 if duration < 0 else 30000 if duration > 30000 else duration
        position = 0 if position < 0 else 1000 if position > 1000 else position
        duration = int(duration)
        position = int(position)
        loVal = int(position & 0xFF)
        hiVal = int(position >> 8)
        loTime = int(duration & 0xFF)
        hiTime = int(duration >> 8)
        self.write(servo_id, HIWONDER_SERVO_MOVE_TIME_WRITE, (loVal, hiVal, loTime, hiTime))

    def set_servos_position(self, duration, args):
        '''
        驱动多个串口舵机转到指定位置(drive the serial servo to rotate to the designated position)
        :use_time: 转动需要的时间(use_time: time taken for rotation)
        :param id: 要驱动的舵机id(param id: the  servo id to be driven)
        :pulse: 位置(pulse: position)
        :param id: 要驱动的舵机id(param id: the  servo id to be driven)
        :pulse: 位置(pulse: position)
        :......
        '''

        if len(args) == 0:
            return
        duration = 0 if duration < 0 else 30000 if duration > 30000 else duration
        loTime = int(duration & 0xFF)
        hiTime = int(duration >> 8)

        packet = []
        for arg in args[0]:
            _id = arg[0]
            _pulse = arg[1]
            buf = bytearray(b'\x55\x55')  # 帧�
            buf.append(_id)  # servo_id
            buf.append(7)  # 指令长度
            buf.append(1)  # 指令

            _pulse = 0 if _pulse < 0 else 1000 if _pulse > 1000 else _pulse
            buf.extend([int(0xff & _pulse), int(0xff & (_pulse >> 8))])  # 分低8位 高8位 放入缓存
            buf.extend([loTime, hiTime])  # 分低8位 高8位 放入缓存

            buf.append(self.checksum(buf))  # 校验和
            packet.extend(buf)
        with self.serial_mutex:
            self.__write_serial(packet)

    def get_servos_position(self, args):
        if len(args) == 0:
            return
        data = []
        for servo_id in args:
            response = self.read(servo_id, HIWONDER_SERVO_POS_READ)
            if response:
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                data.extend([[servo_id, response[5] + (response[6] << 8)]])
        return data

    def stop(self, servo_id):
        '''
        停止舵机运行(stop servo rotation)
        :param id:
        :return:
        '''
        self.write(servo_id, HIWONDER_SERVO_MOVE_STOP, ())

    def set_servo_deviation(self, servo_id, dev=0):
        '''
        调整偏差(adjust deviation)
        :param id: 舵机id(param id: servo id)
        :param d:  偏差(param d:  deviation)
        '''
        self.write(servo_id, HIWONDER_SERVO_ANGLE_OFFSET_ADJUST, (dev,))

    def save_servo_deviation(self, servo_id):
        '''
        配置偏差，掉电保护
        :param id: 舵机id
        '''
        self.write(servo_id, HIWONDER_SERVO_ANGLE_OFFSET_WRITE, ())

    def get_servo_deviation(self, servo_id):
        '''
        读取偏差值(read deviation)
        :param id: servo number
        :return:
        '''
        # 发送读取偏差指令
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_ANGLE_OFFSET_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def set_servo_range(self, servo_id, low, high):
        '''
        设置舵机转动范围(set the servo rotation range)
        :param id:
        :param low:
        :param high:
        :return:
        '''
        low = int(low)
        high = int(high)
        loLow = int(low & 0xFF)
        hiLow = int(low >> 8)
        loHigh = int(high & 0xFF)
        hiHigh = int(high >> 8)
        # self.write(servo_id, HIWONDER_SERVO_ANGLE_LIMIT_WRITE, (loLow, hiLow, loHigh, hiHigh))

    def parse_result(self, data):
        data_len = data[3]
        if data_len == 4:
            return data[5]
        elif data_len == 5:
            return data[5] + (data[6] << 8)
        elif data_len == 7:
            return data[5] + (data[6] << 8), data[7] + (data[8] << 8)
        else:
            return None

    def get_servo_range(self, servo_id):
        '''
        读取舵机转动范围(read the servo rotation range)
        :param id:
        :return: 返回元祖 0： 低位  1： 高位(return: return tuple 0： low-bit  1： high-bit)
        '''
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_ANGLE_LIMIT_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def set_servo_vin_range(self, servo_id, low, high):
        '''
        设置舵机电压范围(set the servo voltage range)
        :param id:
        :param low:
        :param high:
        :return:
        '''
        low = int(low)
        high = int(high)
        loLow = int(low & 0xFF)
        hiLow = int(low >> 8)
        loHigh = int(high & 0xFF)
        hiHigh = int(high >> 8)
        self.write(servo_id, HIWONDER_SERVO_VIN_LIMIT_WRITE, (loLow, hiLow, loHigh, hiHigh))

    def get_servo_vin_range(self, servo_id):
        '''
        读取舵机转动范围(read the servo rotation range)
        :param id:
        :return: 返回元祖 0： 低位  1： 高位(return: return tuple 0： low bit  1： high bit)
        '''
        count = 0
        while True:
            response = self.read(servo_id, HIWONDER_SERVO_VIN_LIMIT_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def set_servo_temp_range(self, servo_id, m_temp):
        '''
        设置舵机最高温度报警
        :param id:
        :param m_temp:
        :return:
        '''
        self.write(servo_id, HIWONDER_SERVO_TEMP_MAX_LIMIT_WRITE, (m_temp,))

    def get_servo_temp_range(self, servo_id):
        '''
        读取舵机温度报警范围(read the servo temperature alarm range)
        :param id:
        :return:
        '''
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_TEMP_MAX_LIMIT_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def get_servo_temp(self, servo_id):
        '''
        读取舵机温度(read the servo temperature)
        :param id:
        :return:
        '''
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_TEMP_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def get_servo_vin(self, servo_id):
        '''
        读取舵机电压(read the servo voltage)
        :param id:
        :return:
        '''
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_VIN_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def reset_servo(self, servo_id):
        # 舵机清零偏差和P值中位（500）(clear servo deviation and center P value)
        self.set_deviation(servo_id, 0)  # 清零偏差(clear deviation)
        time.sleep(0.1)
        self.write(servo_id, HIWONDER_SERVO_MOVE_TIME_WRITE, 500, 100)  # 中位(center the servo)

    def unload_servo(self, servo_id, status):
        self.write(servo_id, HIWONDER_SERVO_LOAD_OR_UNLOAD_WRITE, (status,))

    def get_servo_load_state(self, servo_id):
        count = 0
        while True:
            count += 1
            response = self.read(servo_id, HIWONDER_SERVO_LOAD_OR_UNLOAD_READ)
            if response:
                count = 0
                self.exception_on_error(response[4], servo_id, 'fetching present position')
                return self.parse_result(response)
            if count > self.timeout:
                count = 0
                return None

    def exception_on_error(self, error_code, servo_id, command_failed):
        global exception
        exception = None

        if not isinstance(error_code, int):
            ex_message = '[servo #%d on %s@%sbps]: %s failed' % (
            servo_id, self.ser.port, self.ser.baudrate, command_failed)
            msg = 'Communcation Error ' + ex_message
            exception = NonfatalErrorCodeError(msg, 0)
            return


class SerialOpenError(Exception):
    def __init__(self, port, baud):
        Exception.__init__(self)
        self.message = "Cannot open port '%s' at %d bps" % (port, baud)
        self.port = port
        self.baud = baud

    def __str__(self):
        return self.message


class ChecksumError(Exception):
    def __init__(self, servo_id, response, checksum):
        Exception.__init__(self)
        self.message = 'Checksum received from motor %d does not match the expected one (%d != %d)' \
                       % (servo_id, response[-1], checksum)
        self.response_data = response
        self.expected_checksum = checksum

    def __str__(self):
        return self.message


class FatalErrorCodeError(Exception):
    def __init__(self, message, ec_const):
        Exception.__init__(self)
        self.message = message
        self.error_code = ec_const

    def __str__(self):
        return self.message


class NonfatalErrorCodeError(Exception):
    def __init__(self, message, ec_const):
        Exception.__init__(self)
        self.message = message
        self.error_code = ec_const

    def __str__(self):
        return self.message


class ErrorCodeError(Exception):
    def __init__(self, message, ec_const):
        Exception.__init__(self)
        self.message = message
        self.error_code = ec_const

    def __str__(self):
        return self.message


class DroppedPacketError(Exception):
    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __str__(self):
        return self.message


class UnsupportedFeatureError(Exception):
    def __init__(self, model_id, feature_id):
        Exception.__init__(self)
        if model_id in HIWONDER_SERVO_PARAMS:
            model = HIWONDER_SERVO_PARAMS[model_id]['name']
        else:
            model = 'Unknown'
        self.message = "Feature %d not supported by model %d (%s)" % (feature_id, model_id, model)

    def __str__(self):
        return self.message
