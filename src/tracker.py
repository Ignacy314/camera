import math
import numpy as np
from ultralytics.engine.results import Boxes
from timeit import default_timer as timer
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


class Tracker:
    def __init__(
        self,
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
    ) -> None:
        self.last_track = timer()

        self.locked = None
        self.locked_box = None
        self.correcting = False
        self.last_lock = timer()

        self.coords_lon = coords_lon
        self.coords_lat = coords_lat
        self.coords_new = coords_new
        self.coords_timer = coords_timer
        self.coords_lock = coords_lock

        self.gps_lon = gps_lon
        self.gps_lat = gps_lat
        # self.gps_new = gps_new
        self.gps_lock = gps_lock
        # self.gps_lons = deque(maxlen=20)
        # self.gps_lats = deque(maxlen=20)
        # self.lon = 0.0
        # self.lat = 0.0

        # self.north_angle = 0.0
        self.device_angle = 0.0
        # self.mag_angles = deque(maxlen=20)
        self.mag_angle = mag_angle
        # self.mag_new = mag_new
        # self.mag_lock = mag_lock

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

    # def process_gps_and_mag(self):
    #     with self.gps_lock:
    #         if self.gps_new.value == 1:
    #             self.gps_new.value = 0
    #             self.gps_lons.append(self.gps_lon.value)
    #             self.gps_lats.append(self.gps_lat.value)
    #             self.lon = mean(self.gps_lons)
    #             self.lat = mean(self.gps_lats)

    # with self.mag_lock:
    #     if self.mag_new.value == 1:
    #         self.mag_new.value = 0
    #         self.mag_angles.append(self.mag_angle.value)
    #         self.north_angle = (
    #             self.device_angle - mean(self.mag_angles) - 90
    #         ) % 360

    def angle_offset(self):
        return self.device_angle - self.mag_angle.value - 90

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

        if time - self.last_lock < 1.0:
            return

        with self.coords_lock:
            if self.coords_new.value == 1 and time - self.coords_timer < 2.0:
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
            self.cmd_q.put("a a 0 35 1")
            # self.cmd_q.put("a c -34 100 -100")
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
        (radius, angle_rad) = cart2pol(lon - self.gps_lon, lat - self.gps_lat)
        angle_deg = (math.degrees(angle_rad) + self.angle_offset()) % 360
        # TODO: tilt based on distance?
        self.cmd_q.put(f"a a {angle_deg} 0 1")
