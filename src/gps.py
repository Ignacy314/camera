from collections import deque
import time
from serial import Serial
from pynmeagps import NMEAReader, NMEA_MSGIDS
from statistics import mean


def gps(stop_flag, gps_lon, gps_lat, gps_lock):
    with Serial("/dev/ttyAMA0", timeout=0.25) as stream:
        nmr = NMEAReader(stream)
        lons = deque(maxlen=20)
        lats = deque(maxlen=20)

        while True:
            if stop_flag.value == 1:
                break

            for _, msg in nmr:
                if msg.msgID == "GGA":
                    print(msg)
                    try:
                        lons.append(float(msg.lon))
                        lats.append(float(msg.lat))

                        lon = mean(lons)
                        lat = mean(lats)

                        with gps_lock:
                            gps_lon.value = lon
                            gps_lat.value = lat
                    except Exception:
                        pass

            time.sleep(0.5)
