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

            # _, msgs = nmr.read()

            for msg in nmr:
                print(msg)

            # if msg is not None and msg.lon is not None:
            #     lons.append(float(msg.lon))
            #     lats.append(float(msg.lat))
            #
            #     lon = mean(lons)
            #     lat = mean(lats)
            #
            #     with gps_lock:
            #         gps_lon.value = lon
            #         gps_lat.value = lat

            time.sleep(0.5)
