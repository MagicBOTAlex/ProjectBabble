"""
-------------------------------------------------------------------------------------------------------------
██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗    ██████╗  █████╗ ██████╗ ██████╗ ██╗     ███████╗
██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██║     ██╔════╝
██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║       ██████╔╝███████║██████╔╝██████╔╝██║     █████╗
██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║       ██╔══██╗██╔══██║██╔══██╗██╔══██╗██║     ██╔══╝
██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║       ██████╔╝██║  ██║██████╔╝██████╔╝███████╗███████╗
╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝       ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═════╝ ╚══════╝╚══════╝
--------------------------------------------------------------------------------------------------------------
GUI by: Prohurtz, qdot
Model by: Summer
App model implementation: Prohurtz, Summer

Additional contributors: RamesTheGeneric (dataset synthesizer), dfgHiatus (locale, some other stuff)

Copyright (c) 2023 Project Babble <3
"""

import ctypes
import os
import queue
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import requests
import threading
import asyncio
import logging
from ctypes import c_int

import uvicorn
from assets import ASSETS_DIR
from assets.images import IMAGES_DIR
from babble_model_loader import *
from camera_widget import CameraWidget
from classes.etvr.PB_ComboAPI import PB_ComboAPI
from config import BabbleConfig
from tab import Tab
from osc import VRChatOSCReceiver, VRChatOSC
from general_settings_widget import SettingsWidget
from algo_settings_widget import AlgoSettingsWidget
from calib_settings_widget import CalibSettingsWidget
from utils.misc_utils import ensurePath, os_type, bg_color_highlight, bg_color_clear
from logger import setup_logging
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


winmm = None

if os_type == "Windows":
    try:
        from ctypes import windll

        winmm = windll.winmm
    except OSError:
        print(
            f'\033[91m[ERROR] error.winmm.\033[0m'
        )

os.system("color")  # init ANSI color

# Random environment variable to speed up webcam opening on the MSMF backend.
# https://github.com/opencv/opencv/issues/17687
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
page_url = "https://github.com/Project-Babble/ProjectBabble/releases/latest"
appversion = "Babble v2.0.7"


def timerResolution(toggle):
    if winmm != None:
        if toggle:
            rc = c_int(winmm.timeBeginPeriod(1))
            if rc.value != 0:
                # TIMEERR_NOCANDO = 97
                print(
                    f'\033[93m[WARN] warn.timerRes {rc.value}\033[0m'
                )
        else:
            winmm.timeEndPeriod(1)

class ThreadManager:
    def __init__(self, cancellation_event):
        """Initialize ThreadManager with a cancellation event for signaling threads."""
        self.threads = []  # List of (thread, shutdown_obj) tuples
        self.cancellation_event = cancellation_event
        self.logger = logging.getLogger("ThreadManager")

    def add_thread(self, thread, shutdown_obj=None):
        """Add a thread and its optional shutdown object to the manager."""
        self.threads.append((thread, shutdown_obj))
        thread.start()
        self.logger.debug(f"Started thread: {thread.name}")

    def kill_thread(self, thread):
        if not thread.is_alive():
            return

        # Screw linux support right now. I love linux mint, but i'm angry
        tid = ctypes.c_long(thread.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            tid, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("Failed to kill thread")

    def shutdown_all(self, timeout=5.0):
        """Shutdown all managed threads with a configurable timeout."""
        self.logger.info("Initiiating shutdown of all threads")
        self.cancellation_event.set()  # Signal all threads to stop


        time.sleep(1000) # Gonna give them 1 fucking second to shutdown, or else off with their heads

        # Call shutdown methods on associated objects if available
        for thread, shutdown_obj in self.threads:
            self.kill_thread(thread)

        # Join threads with the specified timeout
        for thread, _ in self.threads:
            if thread.is_alive():
                self.logger.debug(
                    f"Joining thread: {thread.name} with timeout {timeout}s"
                )
                thread.join(timeout=timeout)

        # Remove terminated threads from the list
        self.threads = [(t, s) for t, s in self.threads if t.is_alive()]

        if self.threads:
            self.logger.warning(
                f"{len(self.threads)} threads still alive: {[t.name for t, _ in self.threads]}"
            )
        else:
            self.logger.info("All threads terminated successfully")

def setup_app(babbleCam: CameraWidget):
    babble_app = PB_ComboAPI(babbleCam)
    babble_app.add_routes()
    app = FastAPI()
    app.include_router(babble_app.router)
    app.mount("/", StaticFiles(directory=ASSETS_DIR, html=True))
    app.mount("/images", StaticFiles(directory=IMAGES_DIR))
    
    # Enable CORS for Tauri (localhost:1420)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:1420", "http://127.0.0.1:1420"],  # Allow Tauri frontend
        allow_credentials=True,  # Allow cookies/authenticated requests
        allow_methods=["*"],  # Allow all request methods (GET, POST, PUT, DELETE)
        allow_headers=["*"],  # Allow all headers
    )

    # Check if we're in an existing event loop
    if asyncio.get_event_loop().is_running():
        loop = asyncio.get_running_loop()
        loop.create_task(uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=4422, log_config=None)).serve())
    else:
        uvicorn.run(app, host="0.0.0.0", port=4422, log_config=None)  # Works if no event loop is running

    return app

async def async_main():
    ensurePath()
    setup_logging()

    # Get Configuration
    config: BabbleConfig = BabbleConfig.load()

    config.save()

    # Uncomment for low-level Vive Facial Tracker logging
    # logging.basicConfig(filename='BabbleApp.log', filemode='w', encoding='utf-8', level=logging.INFO)

    cancellation_event = threading.Event()

    timerResolution(True)

    thread_manager = ThreadManager(cancellation_event)

    osc_queue: queue.Queue[tuple[bool, int, int]] = queue.Queue(maxsize=10)
    osc = VRChatOSC(cancellation_event, osc_queue, config)
    osc_thread = threading.Thread(target=osc.run, name="OSCThread")
    thread_manager.add_thread(osc_thread, shutdown_obj=osc)
    cams = [
        CameraWidget(Tab.CAM, config, osc_queue),
    ]
    babbleCam = cams[0] # Hopefully python fucking passes by ref here

    settings = [
        SettingsWidget(Tab.SETTINGS, config, osc_queue),
        AlgoSettingsWidget(Tab.ALGOSETTINGS, config, osc_queue),
        CalibSettingsWidget(Tab.CALIBRATION, config, osc_queue),
    ]

    # I love how this uses an array, then ditches the array idea. I know it is good fore more flexible code, but ugh. (angry)
    if config.cam_display_id in [Tab.CAM]:
        cams[0].start()
    if config.cam_display_id in [Tab.SETTINGS]:
        settings[0].start()
    if config.cam_display_id in [Tab.ALGOSETTINGS]:
        settings[1].start()
    if config.cam_display_id in [Tab.CALIBRATION]:
        settings[2].start()

    # the cam needs to be running before it is passed to the OSC
    if config.settings.gui_ROSC:
        osc_receiver = VRChatOSCReceiver(cancellation_event, config, cams)
        osc_receiver_thread = threading.Thread(
            target=osc_receiver.run, name="OSCReceiverThread"
        )
        thread_manager.add_thread(osc_receiver_thread, shutdown_obj=osc_receiver)

    app = setup_app(babbleCam)

    # Run the main loop
    await main_loop(babbleCam)

    # Cleanup after main loop exits
    timerResolution(False)
    print(
        f'\033[94m[INFO] babble.exit\033[0m'
    )



async def main_loop(babbleCam: CameraWidget):

    while True:

        # Rather than await asyncio.sleep(0), yield control periodically
        await asyncio.sleep(0.001)  # Small sleep to allow other tasks to rundef main():
    asyncio.run(async_main())


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
