from multiprocessing import Manager
from fastapi import APIRouter
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
        return "balls"
        return self.babbleCam.cropped_visualizer

    async def processed_feed(self):
        # return self.babbleCam.processed_visualizer
        return "balls"

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

    def __del__(self):
        self.stop()
        self.config.stop()

    def __repr__(self) -> str:
        return f"<Babble backend running={self.running}>"
