from config import BabbleSettingsConfig
from osc import Tab
from queue import Queue
from threading import Event
import re
from utils.misc_utils import bg_color_highlight, bg_color_clear, is_valid_float_input, is_valid_int_input
from lang_manager import LocaleStringManager as lang


class AlgoSettingsWidget:
    def __init__(
        self, widget_id: Tab, main_config: BabbleSettingsConfig, osc_queue: Queue
    ):

        self.gui_general_settings_layout = f"-GENERALSETTINGSLAYOUT{widget_id}-"
        self.gui_multiply = f"-MULTIPLY{widget_id}-"
        self.gui_model_file = f"-MODLEFILE{widget_id}-"
        self.gui_use_gpu = f"USEGPU{widget_id}"
        self.gui_speed_coefficient = f"-SPEEDCOEFFICIENT{widget_id}-"
        self.gui_min_cutoff = f"-MINCUTOFF{widget_id}-"
        self.gui_inference_threads = f"-THREADS{widget_id}-"
        self.gui_runtime = f"-RUNTIME{widget_id}"
        self.gui_gpu_index = f"GPUINDEX{widget_id}"
        self.calib_deadzone = f"CALIBDEADZONE{widget_id}"
        self.main_config = main_config
        self.config = main_config.settings
        self.osc_queue = osc_queue
        self.runtime_list = ("Default (ONNX)", "ONNX")

        self.cancellation_event = (
            Event()
        )  # Set the event until start is called, otherwise we can block if shutdown is called.
        self.cancellation_event.set()
        self.image_queue = Queue(maxsize=2)

    def started(self):
        return not self.cancellation_event.is_set()

    def start(self):
        # If we're already running, bail
        if not self.cancellation_event.is_set():
            return
        self.cancellation_event.clear()

    def stop(self):
        # If we're not running yet, bail
        if self.cancellation_event.is_set():
            return
        self.cancellation_event.set()

    def render(self, window, event, values):
        # Input validation for the fields
        if event == self.gui_multiply:
            value = values[self.gui_multiply]
            if not is_valid_float_input(value):
                # Invalid input, remove last character
                value = value[:-1]
                window[self.gui_multiply].update(value)
                values[self.gui_multiply] = value

        elif event == self.calib_deadzone:
            value = values[self.calib_deadzone]
            if not is_valid_float_input(value):
                value = value[:-1]
                window[self.calib_deadzone].update(value)
                values[self.calib_deadzone] = value

        elif event == self.gui_inference_threads:
            value = values[self.gui_inference_threads]
            if not is_valid_int_input(value):
                value = value[:-1]
                window[self.gui_inference_threads].update(value)
                values[self.gui_inference_threads] = value

        elif event == self.gui_gpu_index:
            value = values[self.gui_gpu_index]
            if not is_valid_int_input(value):
                value = value[:-1]
                window[self.gui_gpu_index].update(value)
                values[self.gui_gpu_index] = value

        elif event == self.gui_min_cutoff:
            value = values[self.gui_min_cutoff]
            if not is_valid_float_input(value):
                value = value[:-1]
                window[self.gui_min_cutoff].update(value)
                values[self.gui_min_cutoff] = value

        elif event == self.gui_speed_coefficient:
            value = values[self.gui_speed_coefficient]
            if not is_valid_float_input(value):
                value = value[:-1]
                window[self.gui_speed_coefficient].update(value)
                values[self.gui_speed_coefficient] = value

        changed = False

        try:
            if values[self.gui_multiply] != "":
                if self.config.gui_multiply != float(values[self.gui_multiply]):
                    self.config.gui_multiply = float(values[self.gui_multiply])
                    changed = True
        except ValueError:
            pass  # Ignore invalid float conversion

        if self.config.gui_model_file != values[self.gui_model_file]:
            self.config.gui_model_file = values[self.gui_model_file]
            changed = True

        try:
            if values[self.calib_deadzone] != "":
                if self.config.calib_deadzone != float(values[self.calib_deadzone]):
                    self.config.calib_deadzone = float(values[self.calib_deadzone])
                    changed = True
        except ValueError:
            pass  # Ignore invalid float conversion

        if self.config.gui_use_gpu != values[self.gui_use_gpu]:
            self.config.gui_use_gpu = values[self.gui_use_gpu]
            changed = True

        try:
            if values[self.gui_gpu_index] != "":
                if self.config.gui_gpu_index != int(values[self.gui_gpu_index]):
                    self.config.gui_gpu_index = int(values[self.gui_gpu_index])
                    changed = True
        except ValueError:
            pass  # Ignore invalid int conversion

        if self.config.gui_runtime != str(values[self.gui_runtime]):
            self.config.gui_runtime = str(values[self.gui_runtime])
            changed = True

        try:
            if values[self.gui_inference_threads] != "":
                if self.config.gui_inference_threads != int(
                    values[self.gui_inference_threads]
                ):
                    self.config.gui_inference_threads = int(
                        values[self.gui_inference_threads]
                    )
                    changed = True
        except ValueError:
            pass  # Ignore invalid int conversion

        if values[self.gui_min_cutoff] != "":
            if self.config.gui_min_cutoff != values[self.gui_min_cutoff]:
                self.config.gui_min_cutoff = values[self.gui_min_cutoff]
                changed = True

        if values[self.gui_speed_coefficient] != "":
            if self.config.gui_speed_coefficient != values[self.gui_speed_coefficient]:
                self.config.gui_speed_coefficient = values[self.gui_speed_coefficient]
                changed = True

        if changed:
            self.main_config.save()
        self.osc_queue.put(Tab.ALGOSETTINGS)
