import os
import json
import math
import matplotlib

matplotlib.use("QtAgg")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel,
    QWidget,
    QVBoxLayout,
    QDialog,
    QPushButton,
    QComboBox,
    QLabel,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from matplotlib.patches import Rectangle

from config import Config

config = Config()


class LabelDialog(QDialog):
    """Label selection dialog box"""

    def __init__(self, parent):
        super(LabelDialog, self).__init__()
        self.setWindowTitle("Label")
        self.parent = parent

        self.label_idx = 0

        layout = QVBoxLayout()
        label_combobox = QComboBox()
        # edit class labels in config.py

        label_combobox.addItems(config.diagnosis)
        label_combobox.currentIndexChanged.connect(self.index_changed)

        Ok_btn = QPushButton("Ok")
        Ok_btn.clicked.connect(self.ok_pressed)

        layout.addWidget(QLabel("Label Selection"))
        layout.addWidget(label_combobox)
        layout.addWidget(Ok_btn)
        self.setLayout(layout)

    def index_changed(self, i):
        self.label_idx = i
        print("Index Changed")

    def ok_pressed(self):
        self.parent.selected_label = self.label_idx
        self.accept()


class EEGPlotWidget(QWidget):
    def __init__(self, controller, eep):
        super(EEGPlotWidget, self).__init__()
        self.controller = controller
        self.eep = eep
        self.annotation = []
        self.text_annotations = []

        self.selectors = []
        layout = QVBoxLayout()
        self.fig = Figure(figsize=(20, 20), dpi=100)
        self.fig.tight_layout()

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.cid_enter = self.canvas.mpl_connect(
            "axes_enter_event", self.on_enter_event
        )
        self.canvas.mpl_connect("key_press_event", self.on_key_press)
        self.x1 = 0
        self.x2 = 0
        self.y1 = 0
        self.y2 = 0
        self.rect_selector = None

        toolbar = NavigationToolbar2QT(self.canvas, self)
        # Add the canvas to the layout
        layout.addWidget(self.canvas)
        layout.addWidget(toolbar)

        self.setLayout(layout)
        self.show()

    def show_plot(self, raw_eeg, signal_duration):
        """Plot the raw_eeg in the figure"""
        self.signal_duration = signal_duration
        self.fig.clear()
        self.axes = self.eep.create_axes(self.fig, raw_eeg)
        self.eep.plot_signal(raw_eeg, self.axes)

        self.canvas.draw()

    def on_enter_event(self, _):
        """
        set focus on canvas, needed for capturing
        key press events.
        """
        self.canvas.setFocus()

    def on_key_press(self, event):
        """Pan figure using left/right arrow keys"""
        # Get the current x-limits of the plot
        x_lim = self.axes.get_xlim()
        print(f"{x_lim=}")
        if event.key == "left":
            x_lim_left = max(0, x_lim[0] - config.pan_ammount)
            x_lim_right = max(self.eep.max_x_lim, x_lim[1] - config.pan_ammount)
            # set teh new x_limits of the plot
            self.axes.set_xlim(x_lim_left, x_lim_right)

        if event.key == "right":
            x_lim_left = min(
                self.signal_duration - config.pan_ammount, x_lim[0] + config.pan_ammount
            )
            x_lim_right = min(self.signal_duration, x_lim[1] + config.pan_ammount)
            # set the new x_limits of the plot
            self.axes.set_xlim(x_lim_left, x_lim_right)
        self.canvas.draw()

    def attach_selector(self):
        """Attach a rectangle selector to an axes"""

        self.rect_selector = RectangleSelector(
            self.axes,
            self.select_callback,
            drawtype="box",
            useblit=True,
            button=[1],
            minspanx=5,
            minspany=5,
            spancoords="pixels",
            interactive=True,
        )
        # self.selectors.append(self.rect_selector)
        self.rect_selector.set_active(True)

    def select_callback(self, eclick, erelease):
        """Callback for line selection.
        *eclick* and *erelease* are the press and release events.
        https://matplotlib.org/stable/gallery/widgets/rectangle_selector.html
        """
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata

        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2

        print(f"({x1:3.2f}, {y1:3.10f}) --> ({x2:3.2f}, {y2:3.10f})")

    def toggle_selector(self):
        if self.rect_selector and self.rect_selector.active:
            self.selected_label = 0
            print(f"{self.selected_label=}")

            self.rect_selector.set_active(False)
            rect = Rectangle(
                (min(self.x1, self.x2), min(self.y1, self.y2)),
                abs(self.x1 - self.x2),
                abs(self.y1 - self.y2),
                edgecolor="blue",
                linestyle="solid",
                facecolor="none",
                linewidth=2,
                zorder=10,
            )
            label_selection_dialog = LabelDialog(self)

            print(f"{self.y1 / self.eep.scale_factor}")
            print(f"{self.y2 / self.eep.scale_factor}")

            first_ch = max(
                0,
                min(
                    math.ceil(self.y1 / self.eep.scale_factor),
                    math.ceil(self.y2 / self.eep.scale_factor),
                ),
            )

            last_ch = min(
                22,
                max(
                    math.floor(self.y1 / self.eep.scale_factor),
                    math.floor(self.y2 / self.eep.scale_factor),
                ),
            )
            print(f"{first_ch=}")
            print(f"{last_ch=}")

            selected_channels = list(config.montage_pairs.keys())[
                first_ch : last_ch + 1
            ]

            if label_selection_dialog.exec():
                class_label = config.diagnosis[self.selected_label]
                self.annotation.append(
                    {
                        "channels": selected_channels,
                        "start_time": round(self.x1),
                        "stop_time": round(self.x2),
                        "onset": class_label,
                    }
                )
                # set the text of the rectangle, the label class
                text_ann = self.axes.annotate(
                    class_label, (self.x1, self.y2), weight="bold", fontsize=12
                )
                self.text_annotations.append(text_ann)
                self.axes.add_patch(rect)

                print(f"{self.annotation=}")

            self.canvas.draw()

    def render_saved_annotations(self):
        if len(self.annotation) == 0:
            # do nothing
            return

        montage_list = list(config.montage_pairs.keys())

        for selection in self.annotation:
            first_channel = (
                montage_list.index(selection["channels"][-1]) * self.eep.scale_factor
            )
            last_channel = (
                montage_list.index(selection["channels"][0]) * self.eep.scale_factor
            )

            rect = Rectangle(
                (
                    selection["start_time"],
                    first_channel,
                ),
                selection["stop_time"] - selection["start_time"],
                last_channel - first_channel,
                edgecolor="blue",
                linestyle="solid",
                facecolor="none",
                linewidth=2,
                zorder=10,
            )
            self.axes.annotate(
                selection["onset"],
                (selection["start_time"], first_channel),
                weight="bold",
                fontsize=12,
            )

            self.axes.add_patch(rect)

        self.canvas.draw()

        pass

    def undo_selection(self):
        if len(self.annotation):
            self.rect_selector = None
            self.axes.patches.pop()
            self.axes.patches.pop()
            self.annotation.pop()
            last_annotation = self.text_annotations[-1]
            last_annotation.remove()

            self.text_annotations.pop()
            self.canvas.draw()

    def box_select(self):
        self.toggle_selector()
        self.attach_selector()

    def get_num_selectors(self):
        print(f"{len(self.axes.patches)=}")
        return len(self.axes.patches)

    def change_initial_x_lim(self, duration: int):
        """Set the duration of signal visible on the figure at a time"""
        # get the current x_lim value
        x_lim_min = self.axes.get_xlim()[0]

        self.axes.set_xlim(x_lim_min, x_lim_min + duration)
        self.canvas.draw()

    def goto_duration(self, duration: int, signal_duration: int):
        """Move a `duration` seconds in the signal"""
        # get the current display duration length
        duration_length = self.axes.get_xlim()[1] - self.axes.get_xlim()[0]

        duration = min(signal_duration - duration_length, duration)

        # move to `duration` seconds while keeping display limit
        self.axes.set_xlim(duration, duration + duration_length)
        self.canvas.draw()

    def save_annotation(self):
        if not len(self.annotation):
            # if empty do nothing
            print("Empty")
            return
        # get the directory of the EEG file
        eeg_directory = os.path.dirname(self.controller.filename)
        print(f"{eeg_directory=}")
        # get the filename
        file_name = os.path.basename(self.controller.filename).strip().split(".")[0]
        print(f"{file_name=}")

        with open(
            os.path.join(eeg_directory, f"{file_name}.json"), "w"
        ) as annotation_json:
            annotation_json.write(json.dumps(self.annotation))
