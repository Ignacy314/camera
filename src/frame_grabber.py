import cv2
import numpy as np
from multiprocessing import shared_memory


def frame_grabber(shm_name, shape, dtype, lock, stop_flag, new_frame):
    shm = shared_memory.SharedMemory(name=shm_name)
    frame_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

    video_path = "rtsp://admin:1plus2jest3@192.168.3.64:554/Streaming/Channels/103"
    cap = cv2.VideoCapture(video_path)

    frame_width = int(cap.get(3))  # Width of frame

    frame_height = int(cap.get(4))  # Height of frame

    fps = cap.get(cv2.CAP_PROP_FPS)  # Frames per second
    fourcc = cv2.VideoWriter_fourcc(*"XVID")  # Codec
    out = cv2.VideoWriter("../output.avi", fourcc, fps, (frame_width, frame_height))

    while True:
        if stop_flag.value == 1:
            break

        ret, frame = cap.read()
        if not ret:
            continue

        with lock:
            np.copyto(frame_array, frame[::-1, ::-1])
            new_frame.value = 1

        out.write(frame)

    cap.release()
    out.release()
