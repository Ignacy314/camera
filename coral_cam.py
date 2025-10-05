import asyncio
import threading

import cv2
import websockets
from ultralytics import YOLO


class VideoCapture:
    def __init__(self, name):
        self.cap = cv2.VideoCapture(name)
        self.lock = threading.Lock()
        self.t = threading.Thread(target=self._reader)
        self.t.daemon = True
        self.t.start()

    # grab frames as soon as they are available
    def _reader(self):
        while True:
            with self.lock:
                ret = self.cap.grab()
            if not ret:
                break

    # retrieve latest frame
    def read(self):
        with self.lock:
            success, frame = self.cap.retrieve()
        return success, frame


async def main():
    uri = "ws://10.66.66.1:8080/andros/sender"
    async with websockets.connect(uri, ping_interval=None) as websocket:
        # Load the YOLO11 model
        model = YOLO("best_full_integer_quant_edgetpu.tflite")
        # video_path = "5.mp4"
        video_path = "rtsp://admin:1plus2jest3@192.168.1.64:554/Streaming/Channels/102"

        try:
            # cap = cv2.VideoCapture(video_path)
            cap = VideoCapture(video_path)
        except:
            await asyncio.sleep(1)
            cap = cv2.VideoCapture(video_path)
            # cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # cap.set(cv2.CAP_PROP_FPS, 5)
        while cap.cap.isOpened():
            success, frame = cap.read()
            # if not websocket.connected:
            #     print("### reconnecting ###")
            #     await websockets.connect(uri, ping_interval=None)

            if success:
                # Run YOLO11 tracking on the frame, persisting tracks between frames
                results = model.track(frame, persist=True)

                # Visualize the results on the frame
                try:
                    annotated_frame = results[0].plot()
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
                    data = cv2.imencode(".jpg", annotated_frame, encode_param)[1]
                    data = data.tobytes()
                    # data = bytearray(data)
                    await websocket.send(data)
                except websockets.exceptions.ConnectionClosed:
                    print("### reconnecting ###")
                    websocket = await websockets.connect(uri, ping_interval=None)
                except:
                    print("Failed to display frame")
                # boxes = results[0].summary(True)
                # print(boxes)
            await asyncio.sleep(0.33)
        cap.cap.release()


if __name__ == "__main__":
    asyncio.run(main())

# # Load the YOLO11 model
# model = YOLO("best_full_integer_quant_edgetpu.tflite")
#
# # Open the video file
# video_path = "5.mp4"
# cap = cv2.VideoCapture(video_path)
#
# # Loop through the video frames
# while cap.isOpened():
#     # Read a frame from the video
#     success, frame = cap.read()
#
#     if success:
#         # Run YOLO11 tracking on the frame, persisting tracks between frames
#         results = model.track(frame, persist=True)
#
#         # Visualize the results on the frame
#         try:
#             annotated_frame = results[0].plot()
#             encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]
#             data = cv2.imencode(".jpg", annotated_frame, encode_param)[1]
#
#         except:
#             print("Failed to display frame")
#         boxes = results[0].summary(True)
#         print(boxes)
#
#         # Display the annotated frame
#         # cv2.imshow("YOLO11 Tracking", annotated_frame)
#
#         # Break the loop if 'q' is pressed
#         # if cv2.waitKey(1) & 0xFF == ord("q"):
#     #            break
#     else:
#         # Break the loop if the end of the video is reached
#         break
#
# # Release the video capture object and close the display window
# cap.release()
# # cv2.destroyAllWindows()
