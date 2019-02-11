import math
import time

import ustruct  # pylint: disable=E0401
from machine import I2C, Pin  # pylint: disable=E0401

global i2c

EC_SALINITY = 0x3c                  # EC Salinity probe I2C address

EC_MEASURE_EC = 80                  # start an EC measure */
EC_MEASURE_TEMP = 40                # measure temperature */
EC_CALIBRATE_PROBE = 20             # calibrate the probe */
EC_CALIBRATE_LOW = 10               # low point calibration */
EC_CALIBRATE_HIGH = 8               # high point calibration */
EC_I2C = 4                          # Command to change the i2c address */
EC_READ = 2                         # Command to read from EEPROM */
EC_WRITE = 1                        # Command to write to EEPROM */

EC_VERSION_REGISTER = 0             # version register */
EC_MS_REGISTER = 1                  # mS register */
EC_TEMP_REGISTER = 5                # temperature in C register */
EC_SOLUTION_REGISTER = 9            # calibration solution register */
EC_TEMPCOEF_REGISTER = 13           # temperatue coefficient register */
EC_CALIBRATE_REFHIGH_REGISTER = 17  # reference low register */
EC_CALIBRATE_REFLOW_REGISTER = 21   # reference high register */
EC_CALIBRATE_READHIGH_REGISTER = 25  # reading low register */
EC_CALIBRATE_READLOW_REGISTER = 29  # reading high register */
EC_CALIBRATE_OFFSET_REGISTER = 33   # calibration offset */
EC_SALINITY_PSU = 37                # Salinity register */
EC_RAW_REGISTER = 41                # raw count register */
EC_TEMP_COMPENSATION_REGISTER = 45  # temperature compensation register */
EC_BUFFER_REGISTER = 49             # buffer register */
EC_FW_VERSION_REGISTER = 53         # firmware version register */
EC_CONFIG_REGISTER = 54             # config register */
EC_TASK_REGISTER = 55               # task register */

EC_EC_MEASUREMENT_TIME = 750        # delay between EC measurements
EC_TEMP_MEASURE_TIME = 750          # delay for temperature measurement

EC_TEMP_COMPENSATION_CONFIG_BIT = 0  # temperature compensation config bit
EC_DUALPOINT_CONFIG_BIT = 0         # dual point config bit


class uFire_EC(object):
    S = 0
    mS = 0
    uS = 0
    raw = 0
    PPM_500 = 0
    PPM_640 = 0
    PPM_700 = 0
    salinityPSU = 0
    tempC = 0
    tempF = 0
    address = EC_SALINITY
    tempCoefEC = 0.019
    tempCoefSalinity = 0.021

    def __init__(self, sda, scl, address=EC_SALINITY, **kwargs):
        global i2c
        self.address = address
        i2c = I2C(-1, Pin(scl), Pin(sda))

# measurements
    def _measure(self, tempCoefficient, newTemp=None):
        if newTemp is True:
            self.measureTemp()

        self._write_register(EC_TEMPCOEF_REGISTER, tempCoefficient)
        self._send_command(EC_MEASURE_EC)
        time.sleep(EC_EC_MEASUREMENT_TIME / 1000.0)
        self.mS = self._read_register(EC_MS_REGISTER)
        self.raw = self._read_register(EC_RAW_REGISTER)

        if self.raw == 0:
            self.mS = float('inf')

        if math.isinf(self.mS) is not True:
            self.PPM_500 = self.mS * 500
            self.PPM_640 = self.mS * 640
            self.PPM_700 = self.mS * 700
            self.uS = self.mS * 1000
            self.S = self.mS / 1000

            self.salinityPSU = self._read_register(EC_SALINITY_PSU)
        else:
            self.mS = -1
            self.PPM_500 = -1
            self.PPM_640 = -1
            self.PPM_700 = -1
            self.uS = -1
            self.S = -1
            self.salinityPSU = -1

        return self.mS

    def measureEC(self, newTemp=None):
        if newTemp is None:
            return self._measure(self.tempCoefEC, self.usingTemperatureCompensation())
        else:
            return self._measure(self.tempCoefEC, newTemp)

    def measureSalinity(self, newTemp=None):
        if newTemp is None:
            return self._measure(self.tempCoefSalinity, self.usingTemperatureCompensation())
        else:
            return self._measure(self.tempCoefSalinity, newTemp)

    def measureTemp(self):
        self._send_command(EC_MEASURE_TEMP)
        time.sleep(EC_TEMP_MEASURE_TIME / 1000.0)
        self.tempC = self._read_register(EC_TEMP_REGISTER)

        if self.tempC == -127.0:
            self.tempF = -127.0
        else:
            self.tempF = ((self.tempC * 9) / 5) + 32

        return self.tempC

# calibration
    def calibrateProbe(self, solutionEC, tempCoef):
        dualpoint = self.usingDualPoint()
        self.useDualPoint(0)
        self._write_register(EC_TEMPCOEF_REGISTER, tempCoef)
        self._write_register(EC_SOLUTION_REGISTER, solutionEC)
        self._send_command(EC_CALIBRATE_PROBE)
        time.sleep(EC_EC_MEASUREMENT_TIME / 1000.0)
        self.useDualPoint(dualpoint)

    def calibrateProbeLow(self, solutionEC, tempCoef):
        dualpoint = self.usingDualPoint()
        self.useDualPoint(0)
        self._write_register(EC_TEMPCOEF_REGISTER, tempCoef)
        self._write_register(EC_SOLUTION_REGISTER, solutionEC)
        self._send_command(EC_CALIBRATE_LOW)
        time.sleep(EC_EC_MEASUREMENT_TIME / 1000.0)
        self.useDualPoint(dualpoint)

    def calibrateProbeHigh(self, solutionEC, tempCoef):
        dualpoint = self.usingDualPoint()
        self.useDualPoint(0)
        self._write_register(EC_TEMPCOEF_REGISTER, tempCoef)
        self._write_register(EC_SOLUTION_REGISTER, solutionEC)
        self._send_command(EC_CALIBRATE_HIGH)
        time.sleep(EC_EC_MEASUREMENT_TIME / 1000.0)
        self.useDualPoint(dualpoint)

    def getCalibrateOffset(self):
        return self._read_register(EC_CALIBRATE_OFFSET_REGISTER)

    def getCalibrateHighReference(self):
        return self._read_register(EC_CALIBRATE_REFHIGH_REGISTER)

    def getCalibrateLowReference(self):
        return self._read_register(EC_CALIBRATE_REFLOW_REGISTER)

    def getCalibrateHighReading(self):
        return self._read_register(EC_CALIBRATE_READHIGH_REGISTER)

    def getCalibrateLowReading(self):
        return self._read_register(EC_CALIBRATE_READLOW_REGISTER)

    def setCalibrateOffset(self, offset):
        self._write_register(EC_CALIBRATE_OFFSET_REGISTER, offset)

    def setDualPointCalibration(self, refLow, refHigh, readLow, readHigh):
        self._write_register(EC_CALIBRATE_REFLOW_REGISTER, refLow)
        self._write_register(EC_CALIBRATE_REFHIGH_REGISTER, refHigh)
        self._write_register(EC_CALIBRATE_READLOW_REGISTER, readLow)
        self._write_register(EC_CALIBRATE_READHIGH_REGISTER, readHigh)

    def useDualPoint(self, b):
        retval = self._read_byte(EC_CONFIG_REGISTER)
        retval = self._bit_set(retval, EC_DUALPOINT_CONFIG_BIT, b)
        self._write_byte(EC_CONFIG_REGISTER, retval)

# temperature

    def setTemp(self, temp_C):
        self._write_register(EC_TEMP_REGISTER, temp_C)
        self.tempC = temp_C
        self.tempF = ((self.tempC * 9) / 5) + 32

    def setTempConstant(self, b):
        self._write_register(EC_TEMP_COMPENSATION_REGISTER, b)

    def getTempConstant(self):
        return self._read_register(EC_TEMP_COMPENSATION_REGISTER)

    def useTemperatureCompensation(self, b):
        retval = self._read_byte(EC_CONFIG_REGISTER)

        retval = self._bit_set(retval, EC_TEMP_COMPENSATION_CONFIG_BIT, b)
        self._write_byte(EC_CONFIG_REGISTER, retval)

    def usingTemperatureCompensation(self):
        retval = self._read_byte(EC_CONFIG_REGISTER)
        return (retval >> EC_TEMP_COMPENSATION_CONFIG_BIT) & 0x01

    def usingDualPoint(self):
        retval = self._read_byte(EC_CONFIG_REGISTER)
        return (retval >> 0) & 0x01

# utilities
    def getVersion(self):
        return self._read_byte(EC_VERSION_REGISTER)

    def getFirmware(self):
        return self._read_byte(EC_FW_VERSION_REGISTER)

    def reset(self):
        n = float('nan')
        self._write_register(EC_CALIBRATE_OFFSET_REGISTER, n)
        self._write_register(EC_CALIBRATE_REFHIGH_REGISTER, n)
        self._write_register(EC_CALIBRATE_REFLOW_REGISTER, n)
        self._write_register(EC_CALIBRATE_READHIGH_REGISTER, n)
        self._write_register(EC_CALIBRATE_READLOW_REGISTER, n)
        self.setTempConstant(25)
        self.useTemperatureCompensation(False)
        self.useDualPoint(False)

    def setI2CAddress(self, i2cAddress):
        self._write_register(EC_BUFFER_REGISTER, float(i2cAddress))
        self._send_command(EC_I2C)
        self.address = int(i2cAddress)

    def connected(self):
        retval = self._read_byte(EC_VERSION_REGISTER)

        if retval != 0xFF:
            return True
        else:
            return False

    def readEEPROM(self, address):
        self._write_register(EC_SOLUTION_REGISTER, int(address))
        self._send_command(EC_READ)
        return self._read_register(EC_BUFFER_REGISTER)

    def writeEEPROM(self, address, val):
        self._write_register(EC_SOLUTION_REGISTER, int(address))
        self._write_register(EC_BUFFER_REGISTER, float(val))
        self._send_command(EC_WRITE)

    def _bit_set(self, v, index, x):
        mask = 1 << index
        v &= ~mask
        if x:
            v |= mask
        return v

    def _change_register(self, r):
        global i2c
        i2c.write_byte(self.address, r)
        time.sleep(10 / 1000.0)

    def _send_command(self, command):
        global i2c
        i2c.writeto_mem(self.address, EC_TASK_REGISTER, bytearray([command]))
        time.sleep(10 / 1000.0)

    def _write_register(self, reg, f):
        global i2c
        n = self.round_total_digits(f)
        fd = bytearray(ustruct.pack("f", n))
        i2c.writeto_mem(self.address, reg, fd)
        time.sleep(10 / 1000.0)

    def _read_register(self, reg):
        global i2c
        data = [0, 0, 0, 0]
        data[0] = int.from_bytes(i2c.readfrom_mem(self.address, reg, 1), 'big')
        data[1] = int.from_bytes(i2c.readfrom_mem(
            self.address, reg + 1, 1), 'big')
        data[2] = int.from_bytes(i2c.readfrom_mem(
            self.address, reg + 2, 1), 'big')
        data[3] = int.from_bytes(i2c.readfrom_mem(
            self.address, reg + 3, 1), 'big')
        ba = bytearray(data)
        f = ustruct.unpack('f', ba)[0]
        return self.round_total_digits(f)

    def _write_byte(self, reg, val):
        global i2c
        i2c.writeto_mem(self.address, reg, bytearray([val]))
        time.sleep(10 / 1000.0)

    def _read_byte(self, reg):
        global i2c
        return int.from_bytes(i2c.readfrom_mem(self.address, reg, 1), 'big')

    def magnitude(self, x):
        if math.isnan(x):
            return 0
        if math.isinf(x):
            return 0
        return 0 if x == 0 else int(math.floor(math.log(abs(x), 10))) + 1

    def round_total_digits(self, x, digits=7):
        return round(x, digits - self.magnitude(x))