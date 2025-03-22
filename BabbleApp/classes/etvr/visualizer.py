from threading import Thread
import threading
import cv2
import os.path
from typing import Any
from queue import Queue
from fastapi.responses import StreamingResponse
from assets import IMAGES_DIR

OFLINE_IMAGE = cv2.imread(os.path.join(IMAGES_DIR, "communityIcon_quo4g2g0l9861.jpg"))


class Visualizer:
    def __init__(self, image_queue: Queue):
        self.image_queue: Queue = image_queue
        self.running: bool = True
        self.shutdownToken: threading.Event | None = None

    def gen_frame(self):
        while self.running and not self.shutdownToken.is_set():
            try:
                frame = self.image_queue.get(timeout=1)[0]
            except Exception:
                frame = OFLINE_IMAGE
            ret, frame = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + bytearray(frame) + b"\r\n")

    def video_feed(self, shutdownToken: threading.Event) -> StreamingResponse:
        self.shutdownToken = shutdownToken
        return StreamingResponse(self.gen_frame(), media_type="multipart/x-mixed-replace; boundary=frame")

    def stop(self):
        self.running = False

    def __call__(self, *args: Any, **kwds: Any) -> StreamingResponse:
        return self.video_feed()
