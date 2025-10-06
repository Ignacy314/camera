from enum import Enum

import requests
from requests.auth import HTTPDigestAuth


class PtzResponse(Enum):
    TIMEOUT = 1
    CONNECTION = 2
    REQUEST = 3
    OTHER = 4
    OK = 200
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    FORBIDDEN = 403


class PtzControl:
    def __init__(
        self, camera_user, camera_pass, camera_ip="192.168.3.64", camera_port=80
    ) -> None:
        self.absolute_endpoint = (
            f"http://{camera_ip}:{camera_port}/ISAPI/PTZCtrl/channels/1/absolute"
        )
        self.continuous_endpoint = (
            f"http://{camera_ip}:{camera_port}/ISAPI/PTZCtrl/channels/1/continuous"
        )
        self.auth = HTTPDigestAuth(camera_user, camera_pass)

    def send_xml(self, xml_data, endpoint):
        headers = {"Content-Type": "application/xml"}

        try:
            response = requests.put(
                endpoint, headers=headers, data=xml_data, auth=self.auth, timeout=0.25
            )

            if response.status_code == 200:
                return PtzResponse.OK
            else:
                if response.status_code == 401:
                    return PtzResponse.UNAUTHORIZED
                elif response.status_code == 404:
                    return PtzResponse.NOT_FOUND
                elif response.status_code == 403:
                    return PtzResponse.FORBIDDEN
                else:
                    return PtzResponse.OTHER

        except requests.exceptions.Timeout:
            return PtzResponse.TIMEOUT
        except requests.exceptions.ConnectionError:
            return PtzResponse.CONNECTION
        except requests.exceptions.RequestException:
            return PtzResponse.REQUEST
        except Exception:
            return PtzResponse.OTHER

    def absolute(self, pan_degrees, tilt_degrees, zoom_level):
        elevation_val = int(tilt_degrees * 10)
        azimuth_val = int(pan_degrees * 10)
        zoom_val = int(zoom_level * 10)

        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <AbsoluteHigh>
        <elevation>{elevation_val}</elevation>
        <azimuth>{azimuth_val}</azimuth>
        <absoluteZoom>{zoom_val}</absoluteZoom>
    </AbsoluteHigh>
</PTZData>
"""

        return self.send_xml(xml_payload, self.absolute_endpoint)

    def continuous(self, pan, tilt, zoom):
        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <pan>{int(pan)}</pan>
    <tilt>{int(tilt)}</tilt>
    <zoom>{int(zoom)}</zoom>
</PTZData>
"""

        return self.send_xml(xml_payload, self.continuous_endpoint)

    def tilt_cont(self, tilt):
        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <tilt>{tilt}</tilt>
</PTZData>
"""

        return self.send_xml(xml_payload, self.continuous_endpoint)

    def pan_cont(self, pan):
        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <pan>{pan}</pan>
</PTZData>
"""

        return self.send_xml(xml_payload, self.continuous_endpoint)

    def stop(self):
        xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<PTZData>
    <pan>0</pan>
    <tilt>0</tilt>
    <zoom>0</zoom>
</PTZData>
"""

        return self.send_xml(xml_payload, self.continuous_endpoint)
