import time
from ultralytics import YOLO
import numpy as np
from multiprocessing import shared_memory
from tracker import Tracker


def inference(
    in_shm_name,
    out_shm_name,
    shape,
    dtype,
    in_lock,
    out_lock,
    stop_flag,
    in_new_frame,
    out_new_frame,
    coords_x,
    coords_y,
    coords_new,
    coords_lock,
    gps_lon,
    gps_lat,
    gps_new,
    gps_lock,
    mag_north,
    mag_new,
    mag_lock,
    cmd_q,
):
    # yolo export model=yolo11n.pt format=openvino int8=True data=coco128.yaml nms=True
    model = YOLO("best.pt")
    # model = YOLO("best_full_integer_quant_edgetpu.tflite")

    in_shm = shared_memory.SharedMemory(name=in_shm_name)
    frame_array = np.ndarray(shape, dtype=dtype, buffer=in_shm.buf)
    out_shm = shared_memory.SharedMemory(name=out_shm_name)
    plot_array = np.ndarray(shape, dtype=dtype, buffer=out_shm.buf)

    tracker = Tracker(
        coords_x,
        coords_y,
        coords_new,
        coords_lock,
        gps_lon,
        gps_lat,
        gps_new,
        gps_lock,
        mag_north,
        mag_new,
        mag_lock,
        cmd_q,
    )

    while True:
        if stop_flag.value == 1:
            cmd_q.put("stop")
            break

        if in_new_frame.value == 1:
            with in_lock:
                frame = frame_array.copy()
            in_new_frame.value = 0
            results = model.track(frame, persist=True, verbose=False)

            if out_new_frame.value == 0:
                # print("out new frame")
                frame = results[0].plot()
                with out_lock:
                    np.copyto(plot_array, frame)
                out_new_frame.value = 1

            tracker.process_boxes(results[0].boxes)
            # tracker.process_gps_and_mag()
            tracker.track()

        else:
            time.sleep(0.001)
