import time
import asyncio
import websockets
import cv2
import numpy as np
from multiprocessing import shared_memory
from timeit import default_timer as timer


def display(shm_name, shape, dtype, lock, stop_flag, new_frame):
    asyncio.run(_display(shm_name, shape, dtype, lock, stop_flag, new_frame))


async def _display(shm_name, shape, dtype, lock, stop_flag, new_frame):
    shm = shared_memory.SharedMemory(name=shm_name)
    plot_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
    last_frame = timer()

    uri = "ws://localhost:8080/andros/sender"
    while True:
        if stop_flag.value == 1:
            break

        try:
            async with websockets.connect(uri, ping_interval=None) as websocket:
                while True:
                    if stop_flag.value == 1:
                        break

                    if new_frame.value == 1 and timer() - last_frame > 0.1:
                        last_frame = timer()
                        # print("in new frame")
                        with lock:
                            plot = plot_array.copy()
                        new_frame.value = 0

                        try:
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
                            data = cv2.imencode(".jpg", plot, encode_param)[1]
                            data = data.tobytes()
                            await websocket.send(data)
                        except websockets.exceptions.ConnectionClosed:
                            print("### reconnecting ###")
                            websocket = await websockets.connect(
                                uri, ping_interval=None
                            )
                        except Exception:
                            print("Failed to display frame")
                    else:
                        time.sleep(0.001)
        except Exception:
            time.sleep(0.25)
