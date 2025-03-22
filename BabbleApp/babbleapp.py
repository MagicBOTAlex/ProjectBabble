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
from classes.ThreadManager import ThreadManager
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

def setup_app(babbleCam: CameraWidget, thread_manager: ThreadManager):
    babble_app = PB_ComboAPI(babbleCam, thread_manager)
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
        CameraWidget(Tab.CAM, config, osc_queue, thread_manager),
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

    app = setup_app(babbleCam, thread_manager)

    # Run the main loop
    await main_loop(thread_manager)

    # Cleanup after main loop exits
    timerResolution(False)
    print(
        f'\033[94m[INFO] babble.exit\033[0m'
    )



async def main_loop(thread_manager: ThreadManager):

    while not thread_manager.cancellation_event.is_set():

        # Rather than await asyncio.sleep(0), yield control periodically
        await asyncio.sleep(0.001)  # Small sleep to allow other tasks to rundef main():

    print(
        f'\033[94m[INFO] Main exit\033[0m'
    )
    quit()


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
