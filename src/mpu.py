import time
from mpu9250_jmdev.registers import (
    AK8963_ADDRESS,
    MPU9050_ADDRESS_68,
    GFS_1000,
    AFS_8G,
    AK8963_BIT_16,
    AK8963_MODE_C100HZ,
)
from mpu9250_jmdev.mpu_9250 import MPU9250
import numpy as np


def oproj(v, w):
    a = np.dot(v, w) / np.dot(w, w)
    return [v[0] - a * w[0], v[1] - a * w[1], v[2] - a * w[2]]


def calculate_angle(mag, acc):
    vec_north = oproj(mag, acc)

    return -np.atan2(vec_north[1], vec_north[0]) * 180.0 / np.pi


OLD = 0.8


def mpu(
    stop_flag,
    mag_angle,
    mag_new,
    mag_lock,
):
    mpu = MPU9250(
        address_ak=AK8963_ADDRESS,
        address_mpu_master=MPU9050_ADDRESS_68,  # In 0x68 Address
        address_mpu_slave=None,
        bus=1,
        gfs=GFS_1000,
        afs=AFS_8G,
        mfs=AK8963_BIT_16,
        mode=AK8963_MODE_C100HZ,
    )

    # print(mpu.checkAKDataReady())
    # print(mpu.checkMPUDataReady())

    # mpu.calibrate()
    mpu.configure()

    filtered_angle = 0

    while True:
        if stop_flag.value == 1:
            break

        mag = mpu.readMagnetometerMaster()
        acc = mpu.readAccelerometerMaster()
        print("Mag", mag)
        print("Acc", acc)

        new_angle = calculate_angle(mag, acc)
        print("Angle", new_angle)

        filtered_angle = OLD * filtered_angle + (1 - OLD) * new_angle
        print("Filtered angle", filtered_angle)

        with mag_lock:
            mag_new.value = 1
            mag_angle.value = filtered_angle

        time.sleep(0.25)
