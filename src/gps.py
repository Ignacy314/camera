from collections import deque
import time
from serial import Serial
from pynmeagps import NMEAReader
from statistics import mean


def gps(stop_flag, gps_lon, gps_lat, gps_lock):
    with Serial("/dev/ttyAMA0", timeout=0.25) as stream:
        nmr = NMEAReader(stream)
        lons = deque(maxlen=20)
        lats = deque(maxlen=20)

        while True:
            if stop_flag.value == 1:
                break

            _, msg = nmr.read()

            lons.append(msg.lon)
            lats.append(msg.lat)

            lon = mean(lons)
            lat = mean(lats)

            with gps_lock:
                gps_lon.value = lon
                gps_lat.value = lat

            time.sleep(0.5)
