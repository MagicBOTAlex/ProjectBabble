from config import BabbleSettingsConfig
from osc import Tab
from queue import Queue
from threading import Event
import numpy as np
from calib_settings_values import set_shapes
from utils.misc_utils import bg_color_highlight, bg_color_clear, is_valid_float_input


class CalibSettingsWidget:
    def __init__(
        self, widget_id: Tab, main_config: BabbleSettingsConfig, osc_queue: Queue
    ):
        self.gui_general_settings_layout = f"-GENERALSETTINGSLAYOUT{widget_id}-"
        self.gui_reset_min = f"-RESETMIN{widget_id}-"
        self.gui_reset_max = f"-RESETMAX{widget_id}-"
        self.gui_multiply = f"-MULTIPLY{widget_id}-"
        self.gui_calibration_mode = f"-CALIBRATIONMODE{widget_id}-"
        self.main_config = main_config
        self.config = main_config.settings
        self.array = np.fromstring(
            self.config.calib_array.replace("[", "").replace("]", ""), sep=","
        ).reshape(2, 45)
        self.calibration_list = ["Neutral", "Full"]
        self.osc_queue = osc_queue
        self.shape_index, self.shape = set_shapes(widget_id)
        self.refreshed = False

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
        self.array = np.fromstring(
            self.config.calib_array.replace("[", "").replace("]", ""), sep=","
        ).reshape(
            2, 45
        )  # Reload the array from the config
        self.refreshed = False

    def stop(self):
        # If we're not running yet, bail
        if self.cancellation_event.is_set():
            return
        self.cancellation_event.set()

    def render(self, window, event, values):
        # If anything has changed in our configuration settings, change/update those.
        changed = False
        if not self.refreshed:
            for count1, element1 in enumerate(self.shape):
                for count2, element2 in enumerate(element1):
                    window[element2].update(float(self.array[count1][count2]))
                    # values[element2] = float(self.array[count1][count2])
                    self.refreshed = True

        if self.config.calibration_mode != str(values[self.gui_calibration_mode]):
            self.config.calibration_mode = str(values[self.gui_calibration_mode])
            changed = True

        for count1, element1 in enumerate(self.shape):
            for count2, element2 in enumerate(element1):
                if values[element2] != "":   
                    value = values[element2]
                    if is_valid_float_input(value): # Returns true if a single decimal point. Therefore we need to make sure value can be converted to a float by assuming a dot implies a leading 0.
                        if value == ".":
                            valid_float = 0.
                            values[element2] = valid_float
                            window[element2].update(valid_float)
                        value = float(values[element2])
                        if float(self.array[count1][count2]) != value:
                            self.array[count1][count2] = value
                            changed = True
                    else:
                        trimmed_value = value[:-1]
                        if trimmed_value == '':     # If we get an empty string, don't try to convert to float. 
                            window[element2].update(trimmed_value)
                            values[element2] = trimmed_value
                        else: 
                            value = float(trimmed_value)
                            window[element2].update(value)
                            values[element2] = value

        if event == self.gui_reset_min:
            for count1, element1 in enumerate(self.shape):
                for count2, element2 in enumerate(element1):
                    self.array[0][count2] = float(0)
                    changed = True
                    self.refreshed = False
                    
        elif event == self.gui_reset_max:
            for count1, element1 in enumerate(self.shape):
                for count2, element2 in enumerate(element1):
                    self.array[1][count2] = float(1)
                    changed = True
                    self.refreshed = False

        if changed:
            self.config.calib_array = np.array2string(self.array, separator=",")
            self.main_config.save()
            # print(self.main_config)
        self.osc_queue.put(Tab.CALIBRATION)
