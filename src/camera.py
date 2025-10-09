import numpy as np
import multiprocessing
from multiprocessing import shared_memory, Lock, Value
from timeit import default_timer as timer

from coords_recv import coords_recv
from frame_grabber import frame_grabber
from inference import inference
from display import display
from control import control
from mpu import mpu
from gps import gps

if __name__ == "__main__":
    shape = (1440, 2560, 3)
    # shape = (1080, 1920, 3)
    # shape = (720, 1280, 3)
    # shape = (576, 704, 3)
    dtype = np.uint8

    in_shm = shared_memory.SharedMemory(
        create=True, size=int(np.prod(shape) * np.dtype(dtype).itemsize)
    )
    in_lock = Lock()

    out_shm = shared_memory.SharedMemory(
        create=True, size=int(np.prod(shape) * np.dtype(dtype).itemsize)
    )
    out_lock = Lock()

    in_new_frame = Value("i", 0)
    out_new_frame = Value("i", 0)

    coords_lon = Value("f", 0)
    coords_lat = Value("f", 0)
    coords_new = Value("i", 0)
    coords_timer = timer()
    coords_lock = Lock()

    gps_lon = Value("f", 0)
    gps_lat = Value("f", 0)
    # gps_new = Value("i", 0)
    gps_lock = Lock()

    mag_angle = Value("f", 0)
    mag_new = Value("i", 0)
    mag_lock = Lock()

    cmd_q = multiprocessing.Queue(1)

    stop_flag = Value("i", 0)

    p1 = multiprocessing.Process(
        target=frame_grabber,
        args=(in_shm.name, shape, dtype, in_lock, stop_flag, in_new_frame),
    )
    p2 = multiprocessing.Process(
        target=inference,
        args=(
            in_shm.name,
            out_shm.name,
            shape,
            dtype,
            in_lock,
            out_lock,
            stop_flag,
            in_new_frame,
            out_new_frame,
            coords_lon,
            coords_lat,
            coords_new,
            coords_timer,
            coords_lock,
            gps_lon,
            gps_lat,
            # gps_new,
            gps_lock,
            mag_angle,
            # mag_new,
            # mag_lock,
            cmd_q,
        ),
    )
    p3 = multiprocessing.Process(
        target=display,
        args=(out_shm.name, shape, dtype, out_lock, stop_flag, out_new_frame),
    )
    p4 = multiprocessing.Process(target=control, args=(cmd_q,))
    p5 = multiprocessing.Process(
        target=mpu, args=(stop_flag, mag_angle, mag_new, mag_lock)
    )
    p6 = multiprocessing.Process(
        target=gps, args=(stop_flag, gps_lon, gps_lat, gps_lock)
    )
    p7 = multiprocessing.Process(
        target=coords_recv,
        args=(
            stop_flag,
            coords_lon,
            coords_lat,
            coords_new,
            coords_timer,
            coords_lock,
        ),
    )

    try:
        for p in (p1, p2, p3, p4, p5, p6, p7):
            p.start()

        while True:
            cmd = input()
            if cmd == "q":
                stop_flag.value = 1
                break
            else:
                cmd_q.put(cmd)

        for p in (p1, p2, p3, p4, p5, p6, p7):
            p.join()
    finally:
        for shm in (in_shm, out_shm):
            shm.close()
            shm.unlink()
