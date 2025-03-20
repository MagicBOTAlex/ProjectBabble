from collections import deque
from queue import Queue, Empty
from threading import Event, Thread
import FreeSimpleGUI as sg
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
from lang_manager import LocaleStringManager as lang

class CameraWidget:
    def __init__(self, widget_id: Tab, main_config: BabbleConfig, osc_queue: Queue):
        self.gui_camera_addr = f"-CAMERAADDR{widget_id}-"
        self.gui_rotation_slider = f"-ROTATIONSLIDER{widget_id}-"
        self.gui_roi_button = f"-ROIMODE{widget_id}-"
        self.gui_roi_layout = f"-ROILAYOUT{widget_id}-"
        self.gui_roi_selection = f"-GRAPH{widget_id}-"
        self.gui_tracking_button = f"-TRACKINGMODE{widget_id}-"
        self.gui_autoroi = f"-AUTOROI{widget_id}-"
        self.gui_save_tracking_button = f"-SAVETRACKINGBUTTON{widget_id}-"
        self.gui_tracking_layout = f"-TRACKINGLAYOUT{widget_id}-"
        self.gui_tracking_image = f"-IMAGE{widget_id}-"
        self.gui_tracking_fps = f"-TRACKINGFPS{widget_id}-"
        self.gui_tracking_bps = f"-TRACKINGBPS{widget_id}-"
        self.gui_output_graph = f"-OUTPUTGRAPH{widget_id}-"
        self.gui_restart_calibration = f"-RESTARTCALIBRATION{widget_id}-"
        self.gui_stop_calibration = f"-STOPCALIBRATION{widget_id}-"
        self.gui_mode_readout = f"-APPMODE{widget_id}-"
        self.gui_roi_message = f"-ROIMESSAGE{widget_id}-"
        self.gui_vertical_flip = f"-VERTICALFLIP{widget_id}-"
        self.gui_horizontal_flip = f"-HORIZONTALFLIP{widget_id}-"
        self.use_calibration = f"-USECALIBRATION{widget_id}-"
        self.gui_refresh_button = f"-REFRESHCAMLIST{widget_id}-"
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
                f'\033[91m[{lang._instance.get_string("log.warn")}] {lang._instance.get_string("error.improperTabValue")}\033[0m'
            )

        self.cancellation_event = Event()
        # Set the event until start is called, otherwise we can block if shutdown is called.
        self.cancellation_event.set()
        self.capture_event = Event()
        self.capture_queue = Queue(maxsize=10)
        self.roi_queue = Queue(maxsize=10)
        self.image_queue = Queue(maxsize=500) # This is needed to prevent the UI from freezing during widget changes. (Alex: doens't work when camera disconnected. I'm still mad)

        self.cropped_visualizer = Visualizer(self.roi_queue)

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

        button_color = "#539e8a"
        self.roi_layout = [
            [
                sg.Button(
                    lang._instance.get_string("camera.selectEntireFrame"),
                    key=self.gui_autoroi,
                    button_color=button_color,
                    tooltip=lang._instance.get_string(
                        "camera.selectEntireFrameTooltip"
                    ),
                ),
            ],
            [
                sg.Graph(
                    (MAX_RESOLUTION, MAX_RESOLUTION),
                    (0, MAX_RESOLUTION),
                    (MAX_RESOLUTION, 0),
                    key=self.gui_roi_selection,
                    drag_submits=True,
                    enable_events=True,
                    background_color=bg_color_highlight,
                )
            ],
        ]

        # Define the window's contents
        self.tracking_layout = [
            [
                sg.Text(
                    lang._instance.get_string("camera.rotation"),
                    background_color=bg_color_highlight,
                ),
                sg.Slider(
                    range=(0, 360),
                    default_value=self.config.rotation_angle,
                    orientation="h",
                    key=self.gui_rotation_slider,
                    background_color=bg_color_highlight,
                    tooltip=lang._instance.get_string("camera.rotationTooltip"),
                ),
            ],
            [
                sg.Button(
                    lang._instance.get_string("camera.startCalibration"),
                    key=self.gui_restart_calibration,
                    button_color=button_color,
                    tooltip=lang._instance.get_string("camera.startCalibrationTooltip"),
                    disabled=not self.settings_config.use_calibration,
                ),
                sg.Button(
                    lang._instance.get_string("camera.stopCalibration"),
                    key=self.gui_stop_calibration,
                    button_color=button_color,
                    tooltip=lang._instance.get_string("camera.startCalibrationTooltip"),
                    disabled=not self.settings_config.use_calibration,
                ),
            ],
            [
                sg.Checkbox(
                    f'{lang._instance.get_string("camera.enableCalibration")}:',
                    default=self.settings_config.use_calibration,
                    key=self.use_calibration,
                    background_color=bg_color_highlight,
                    tooltip=lang._instance.get_string(
                        "camera.enableCalibrationTooltip"
                    ),
                    enable_events=True,
                ),
            ],
            [
                sg.Text(
                    f'{lang._instance.get_string("camera.mode")}:',
                    background_color=bg_color_highlight,
                ),
                sg.Text(
                    lang._instance.get_string("camera.calibrating"),
                    key=self.gui_mode_readout,
                    background_color=button_color,
                ),
                sg.Text(
                    "", key=self.gui_tracking_fps, background_color=bg_color_highlight
                ),
                sg.Text(
                    "", key=self.gui_tracking_bps, background_color=bg_color_highlight
                ),
            ],
            [
                sg.Checkbox(
                    f'{lang._instance.get_string("camera.verticalFlip")}:',
                    default=self.config.gui_vertical_flip,
                    key=self.gui_vertical_flip,
                    background_color=bg_color_highlight,
                    tooltip=f'{lang._instance.get_string("camera.verticalFlipTooltip")}.',
                ),
                sg.Checkbox(
                    f'{lang._instance.get_string("camera.horizontalFlip")}:',
                    default=self.config.gui_horizontal_flip,
                    key=self.gui_horizontal_flip,
                    background_color=bg_color_highlight,
                    tooltip=f'{lang._instance.get_string("camera.horizontalFlipTooltip")}:',
                ),
            ],
            [sg.Image(filename="", key=self.gui_tracking_image)],
            [
                sg.Text(
                    f'{lang._instance.get_string("camera.crop")}:',
                    key=self.gui_roi_message,
                    background_color=bg_color_highlight,
                    visible=False,
                ),
            ],
        ]

        self.widget_layout = [
            [
                sg.Text(
                    lang._instance.get_string("camera.cameraAddress"),
                    background_color=bg_color_highlight,
                ),
                sg.InputCombo(
                    values=self.camera_list,
                    default_value=self.config.capture_source,
                    key=self.gui_camera_addr,
                    tooltip=lang._instance.get_string("camera.cameraAddressTooltip"),
                    enable_events=True,
                    size=(20,0),
                ),
                sg.Button(
                    lang._instance.get_string("camera.refreshCameraList"),
                    key=self.gui_refresh_button,
                    button_color=button_color,
                ),
            ],
            [
                sg.Button(
                    lang._instance.get_string("camera.saveAndRestartTracking"),
                    key=self.gui_save_tracking_button,
                    button_color=button_color,
                ),
            ],
            [
                sg.Button(
                    lang._instance.get_string("camera.trackingMode"),
                    key=self.gui_tracking_button,
                    button_color=button_color,
                    tooltip=f'{lang._instance.get_string("camera.trackingModeTooltip")}.',
                ),
                sg.Button(
                    lang._instance.get_string("camera.croppingMode"),
                    key=self.gui_roi_button,
                    button_color=button_color,
                    tooltip=f'{lang._instance.get_string("camera.croppingModeToolTip")}.',
                ),
            ],
            [
                sg.Column(
                    self.tracking_layout,
                    key=self.gui_tracking_layout,
                    background_color=bg_color_highlight,
                ),
                sg.Column(
                    self.roi_layout,
                    key=self.gui_roi_layout,
                    background_color=bg_color_highlight,
                    visible=False,
                ),
            ],
        ]

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
        self.babble_cnn_thread.start()
        # self.babble_landmark_thread = Thread(target=self.babble_landmark.run)
        # self.babble_landmark_thread.start()
        self.camera_thread = Thread(target=self.camera.run)
        self.camera_thread.start()
        

    def stop(self):
        # If we're not running yet, bail
        if self.cancellation_event.is_set():
            return
        self.cancellation_event.set()
        self.babble_cnn_thread.join()
        # self.babble_landmark_thread.join()
        self.camera_thread.join()

    def render(self, window):
        (maybe_image, cam_info) = self.image_queue.get(block=False)
        imgbytes = cv2.imencode(".ppm", maybe_image)[1].tobytes()
        window[self.gui_tracking_image].update(data=imgbytes)