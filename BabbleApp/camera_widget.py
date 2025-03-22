from collections import deque
from queue import Queue, Empty
from threading import Event, Thread
from classes.ThreadManager import ThreadManager
from classes.etvr.visualizer import Visualizer
import cv2
import os
from babble_processor import BabbleProcessor, CamInfoOrigin
from camera import Camera, CameraState, MAX_RESOLUTION
from config import BabbleConfig
from osc import Tab
from utils.misc_utils import (
    playSound,
    list_camera_names,
    get_camera_index_by_name,
    bg_color_highlight,
    bg_color_clear,
    is_valid_int_input
)

class CameraWidget:
    def __init__(self, widget_id: Tab, main_config: BabbleConfig, osc_queue: Queue, thread_manager: ThreadManager):
        self.thread_manager = thread_manager
        self.osc_queue = osc_queue
        self.main_config = main_config
        self.cam_id = widget_id
        self.settings_config = main_config.settings
        self.config = main_config.cam
        self.settings = main_config.settings
        self.camera_list = list_camera_names()
        self.maybe_image = None
        if self.cam_id == Tab.CAM:
            self.config = main_config.cam
        else:
            raise RuntimeError(
                f'\033[91m[WARN] error.improperTabValue\033[0m'
            )

        self.cancellation_event = Event()
        # Set the event until start is called, otherwise we can block if shutdown is called.
        self.cancellation_event.set()
        self.capture_event = Event()
        self.capture_queue = Queue(maxsize=10)
        self.image_queue = Queue(maxsize=500) # This is needed to prevent the UI from freezing during widget changes. (Alex: doens't work when camera disconnected. I'm still mad)


        self.babble_cnn = BabbleProcessor(
            self.config,
            self.settings_config,
            self.main_config,
            self.cancellation_event,
            self.capture_event,
            self.capture_queue,
            self.image_queue,
            self.cam_id,
            self.osc_queue,
        )

        self.camera_status_queue = Queue(maxsize=2)
        self.camera = Camera(
            self.config,
            0,
            self.cancellation_event,
            self.capture_event,
            self.camera_status_queue,
            self.capture_queue,
            self.settings,
        )

        self.x0, self.y0 = None, None
        self.x1, self.y1 = None, None
        self.figure = None
        self.is_mouse_up = True
        self.in_roi_mode = False
        self.bps = 0

    def _movavg_fps(self, next_fps):
        # next_fps is already averaged
        return f"{round(next_fps)} FPS {round((1 / next_fps if next_fps else 0) * 1000)} ms"

    def _movavg_bps(self, next_bps):
        self.bps = round(0.02 * next_bps + 0.98 * self.bps)
        return f"{self.bps * 0.001 * 0.001 * 8:.3f} Mbps"

    def started(self):
        return not self.cancellation_event.is_set()

    def start(self):
        # If we're already running, bail
        if not self.cancellation_event.is_set():
            return
        self.cancellation_event.clear()
        self.babble_cnn_thread = Thread(target=self.babble_cnn.run)
        self.thread_manager.add_thread(self.babble_cnn_thread)
        # self.babble_landmark_thread = Thread(target=self.babble_landmark.run)
        # self.babble_landmark_thread.start()
        self.camera_thread = Thread(target=self.camera.run)
        self.thread_manager.add_thread(self.camera_thread)
        print("Started camera thread")
        

    def stop(self):
        # If we're not running yet, bail
        if self.cancellation_event.is_set():
            return
        self.cancellation_event.set()
        self.babble_cnn_thread.join()
        # self.babble_landmark_thread.join()
        self.camera_thread.join()