import json
from multiprocessing import Manager
from typing import Optional
from fastapi import APIRouter, Query, Request
import sys

from camera_widget import CameraWidget

import logging

logger = logging.getLogger(__name__)

class PB_ComboAPI:
    def __init__(self, babbleCam: CameraWidget):
        self.running: bool = False
        self.router: APIRouter = APIRouter()
        self.babbleCam = babbleCam;
        self.babbleCam.start();

    async def raw_feed(self):
        return self.babbleCam.babble_cnn.raw_visualizer.video_feed()
    
    async def cropped_feed(self):
        return self.babbleCam.cropped_visualizer.video_feed()

    async def processed_feed(self):
        return self.babbleCam.babble_cnn.processed_visualizer.video_feed()
    
    async def startCalibration(self, caliSamples: Optional[int] = None):
        if caliSamples is not None:
            try:
                caliSamples = int(caliSamples)
            except ValueError:
                return {"error": "Invalid value for caliSamples. Must be a number."}, 400

            self.babbleCam.babble_cnn.calibration_frame_counter = caliSamples
            return {"message": "Calibration started with target samples", "caliSamples": caliSamples}
        
        self.babbleCam.babble_cnn.calibration_frame_counter = 300
        return {"message": "Calibration started targeting 300 samples"}

    async def getCalibrationStatus(self):
        return self.babbleCam.babble_cnn.calibration_frame_counter

    async def setCalibrationState(self, targetState: int):
        newState = targetState > 0
        self.babbleCam.babble_cnn.settings.use_calibration = newState
        return {"message": "State changed to " + ("enabled" if newState else "disabled")} # EWWW python gross. why does it have to be different compared to fucking everythign else

    def add_routes(self) -> None:
        # region: Image streaming endpoints
        self.router.add_api_route(
            name="Get raw camera feed before ROI cropping",
            tags=["streaming"],
            path="/camera/raw/",
            endpoint=self.raw_feed,
            methods=["GET"],
        )
        self.router.add_api_route(
            name="Get cropped camera feed",
            tags=["streaming"],
            path="/camera/cropped/",
            endpoint=self.cropped_feed,
            methods=["GET"],
        )
        self.router.add_api_route(
            name="Get cropped camera feed",
            tags=["streaming"],
            path="/camera/processed/",
            endpoint=self.processed_feed,
            methods=["GET"],
        )

        self.router.add_api_route(
            name="Start babble calibration",
            tags=["calibration"],
            path="/calibrate/start",
            endpoint=self.startCalibration,
            methods=["GET"],
        )
        self.router.add_api_route(
            name="Get babble calibration status",
            tags=["calibration"],
            path="/calibrate/status",
            endpoint=self.getCalibrationStatus,
            methods=["GET"],
        )
        self.router.add_api_route(
            name="Sets if calibration should be used",
            tags=["calibration"],
            path="/calibrate/set",
            endpoint=self.setCalibrationState,
            methods=["GET"],
        )

    def __del__(self):
        self.stop()
        self.config.stop()

    def __repr__(self) -> str:
        return f"<Babble backend running={self.running}>"
