import math
import time
import asyncio
from ultralytics import YOLO
from ultralytics.engine.results import Boxes
import websockets
import cv2
import numpy as np
import multiprocessing
from multiprocessing import shared_memory, Lock, Value
from timeit import default_timer as timer
from camera_control import PtzControl, PtzResponse
from collections import deque
from statistics import mean


def cart2pol(x, y):
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    return (rho, phi)


def pol2cart(rho, phi):
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return (x, y)


def frame_grabber(shm_name, shape, dtype, lock, stop_flag, new_frame):
    shm = shared_memory.SharedMemory(name=shm_name)
    frame_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

    video_path = "rtsp://admin:1plus2jest3@192.168.1.64:554/Streaming/Channels/103"
    cap = cv2.VideoCapture(video_path)

    while True:
        if stop_flag.value == 1:
            break

        ret, frame = cap.read()
        if not ret:
            continue

        with lock:
            np.copyto(frame_array, frame[::-1, ::-1])
            new_frame.value = 1


class Tracker:
    def __init__(
        self,
        coords_lon,
        coords_lat,
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
    ) -> None:
        self.last_track = timer()

        self.locked = None
        self.locked_box = None
        self.correcting = False
        self.last_lock = timer()

        self.coords_lon = coords_lon
        self.coords_lat = coords_lat
        self.coords_new = coords_new
        self.coords_lock = coords_lock
        self.coords_timer = timer()

        self.gps_lon = gps_lon
        self.gps_lat = gps_lat
        self.gps_new = gps_new
        self.gps_lock = gps_lock
        self.gps_lons = deque(maxlen=20)
        self.gps_lats = deque(maxlen=20)
        self.lon = 0.0
        self.lat = 0.0

        self.north_angle = 0.0
        self.device_angle = 0.0
        self.mag_norths = deque(maxlen=20)
        self.mag_north = mag_north
        self.mag_new = mag_new
        self.mag_lock = mag_lock

        self.patrolling = False
        self.patrol_start = None
        self.last_tilt_change = timer()
        self.last_tilt_dir = 1

        self.cmd_q = cmd_q

        self.targets = dict()

    def process_boxes(self, boxes: Boxes):
        # print(boxes)
        if boxes and boxes.is_track:
            bounds = boxes.xywhn.cpu()
            track_ids = boxes.id.int().cpu().tolist()
            confs = boxes.conf.cpu()

            for id in list(self.targets.keys()):
                if id not in track_ids:
                    del self.targets[id]

            if self.locked is not None and self.locked not in track_ids:
                self.locked = None
                self.correcting = False

            for id, conf in zip(track_ids, confs):
                if conf > 0.4:
                    self.targets[id] = self.targets.get(id, 0) + 1

            if self.locked is None:
                maxi = 0
                for id, count in self.targets.items():
                    if count >= 3 and count > maxi:
                        maxi = count
                        self.locked = id

            for box, id in zip(bounds, track_ids):
                if id == self.locked:
                    self.locked_box = box
                    break

        else:
            self.locked = None

    def process_gps_and_mag(self):
        with self.gps_lock:
            if self.gps_new.value == 1:
                self.gps_new.value = 0
                self.gps_lons.append(self.gps_lon.value)
                self.gps_lats.append(self.gps_lat.value)
                self.lon = mean(self.gps_lons)
                self.lat = mean(self.gps_lats)

        with self.mag_lock:
            if self.mag_new.value == 1:
                self.mag_new.value = 0
                self.mag_norths.append(self.mag_north.value)
                self.north_angle = (
                    self.device_angle - mean(self.mag_norths) - 90
                ) % 360

    def track(self):
        time = timer()
        if time - self.last_track < 0.1:
            return
        self.last_track = time
        speed = -34
        print(f"track: {self.locked}")
        if self.locked is not None:
            self.patrol_start = None
            x, y, w, h = self.locked_box
            pan = 0
            tilt = 0
            # TODO: zoom based on w, h?

            if self.correcting:
                if x > 0.6:
                    pan = speed
                elif x < 0.4:
                    pan = -1 * speed

                if y > 0.6:
                    tilt = -1 * speed
                elif y < 0.4:
                    tilt = speed

                self.cmd_q.put(f"a c {pan} {tilt} 0")
                if pan == 0 and tilt == 0:
                    self.correcting = False

                return

            if x > 0.6:
                pan = speed
            elif x < 0.4:
                pan = -1 * speed

            if y > 0.6:
                tilt = -1 * speed
            elif y < 0.4:
                tilt = speed

            self.cmd_q.put(f"a c {pan} {tilt} 0")

            if pan != 0 or tilt != 0:
                self.correcting = True

            return

        if time - self.last_lock < 0.5:
            return

        with self.coords_lock:
            if self.coords_new.value == 1:
                self.patrol_start = None
                self.coords_new.value = 0
                self.coords_timer = time
                self.move_to_coords(self.coords_lon.value, self.coords_lat.value)
                return

        if time - self.coords_timer < 2.0:
            self.patrol_start = None
            # not locked on and there was recently a coordinate to target
            # so don't start patrolling for a time
            return

        if self.patrol_start is None:
            # self.patrolling = False
            self.patrol_start = time
            # self.cmd_q.put("a a 0 30 1")
            self.cmd_q.put("a c -34 100 -100")
            return

        if time - self.patrol_start < 2.0:
            # already patrolling or started patrolling recently, wait for tilt to finish adjusting
            return

        if time - self.last_tilt_change > 2:
            self.last_tilt_change = time
            self.last_tilt_dir *= -1
        tilt = self.last_tilt_dir * 34
        self.cmd_q.put(f"a c -34 {tilt} 0")
        # self.patrolling = True

        return

    def move_to_coords(self, lon, lat):
        (radius, angle_rad) = cart2pol(lon - self.lon, lat - self.lat)
        angle_deg = (math.degrees(angle_rad) + self.north_angle) % 360
        # TODO: tilt based on distance?
        self.cmd_q.put(f"a a {angle_deg} 0 1")


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


def _display(shm_name, shape, dtype, lock, stop_flag, new_frame):
    asyncio.run(display(shm_name, shape, dtype, lock, stop_flag, new_frame))


async def display(shm_name, shape, dtype, lock, stop_flag, new_frame):
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


def control(cmd_q):
    cam = PtzControl("admin", "1plus2jest3")
    manual = False

    while True:
        cmd = cmd_q.get()
        print(f"control: cmd = '{cmd}'")

        if cmd == "stop":
            cmd_cont(cam, [0, 0, 0])
            break

        cmd = cmd.split(" ")
        sub_cmd = cmd[0]

        if sub_cmd == "m":
            sub_cmd = cmd[1]
            if sub_cmd == "on":
                manual = True
            elif sub_cmd == "off":
                manual = False
            elif sub_cmd == "c":
                cmd_cont(cam, cmd[2:])
            elif sub_cmd == "a":
                cmd_abs(cam, cmd[2:])
        elif sub_cmd == "a" and not manual:
            sub_cmd = cmd[1]
            if sub_cmd == "c":
                cmd_cont(cam, cmd[2:])
            elif sub_cmd == "a":
                cmd_abs(cam, cmd[2:])


def cmd_cont(cam, vals):
    try:
        resp = cam.continuous(float(vals[0]), float(vals[1]), float(vals[2]))
        if resp != PtzResponse.OK:
            print(resp)
    except Exception:
        pass


def cmd_abs(cam, vals):
    try:
        resp = cam.absolute(float(vals[0]), float(vals[1]), float(vals[2]))
        if resp != PtzResponse.OK:
            print(resp)
    except Exception:
        pass


if __name__ == "__main__":
    # shape = (1440, 2560, 3)
    shape = (1080, 1920, 3)
    # shape = (720, 1280, 3)
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
    coords_lock = Lock()

    gps_lon = Value("f", 0)
    gps_lat = Value("f", 0)
    gps_new = Value("i", 0)
    gps_lock = Lock()

    mag_north = Value("f", 0)
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
            coords_lock,
            gps_lon,
            gps_lat,
            gps_new,
            gps_lock,
            mag_north,
            mag_new,
            mag_lock,
            cmd_q,
        ),
    )
    p3 = multiprocessing.Process(
        target=_display,
        args=(out_shm.name, shape, dtype, out_lock, stop_flag, out_new_frame),
    )
    p4 = multiprocessing.Process(target=control, args=(cmd_q,))

    try:
        for p in (p1, p2, p3, p4):
            p.start()

        while True:
            cmd = input()
            if cmd == "q":
                stop_flag.value = 1
                break
            else:
                cmd_q.put(cmd)

        for p in (p1, p2, p3):
            p.join()
    finally:
        for shm in (in_shm, out_shm):
            shm.close()
            shm.unlink()
