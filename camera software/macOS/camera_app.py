"""
MEGAPIXEL USB Camera Control GUI for macOS

A PyQt6-based GUI application that controls a USB camera to record videos.
Features:
  - Dropdown to select from available cameras with availability testing
  - Slider to set video recording duration (default: 2 minutes)
  - Folder path selector with automatic filename based on date/time
  - Start button enabled only when all settings are configured
  - Fully asynchronous camera testing and recording to avoid freezing the UI.
"""

import os
import sys
from datetime import datetime
import cv2

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QSlider, QLineEdit, QFileDialog,
    QGroupBox, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

def get_available_cameras(max_index=10):
    cameras = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            cameras.append(index)
            cap.release()
    return cameras

def test_camera(index):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return False
    ret, _ = cap.read()
    cap.release()
    return ret

def generate_video_filename(folder_path, extension=".avi"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{timestamp}{extension}"
    return os.path.join(folder_path, filename)

class CameraScannerThread(QThread):
    finished = pyqtSignal(list)
    
    def run(self):
        cameras = get_available_cameras()
        self.finished.emit(cameras)

class CameraTesterThread(QThread):
    finished = pyqtSignal(int, bool)
    
    def __init__(self, index):
        super().__init__()
        self.index = index
        
    def run(self):
        result = test_camera(self.index)
        self.finished.emit(self.index, result)

class CameraRecorderThread(QThread):
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished_recording = pyqtSignal(str)

    def __init__(self, index, output_path, duration_seconds):
        super().__init__()
        self.index = index
        self.output_path = output_path
        self.duration_seconds = duration_seconds
        self.is_recording = False

    def run(self):
        self.is_recording = True
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            self.error.emit("Failed to open camera.")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 30.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width == 0 or height == 0:
            width, height = 640, 480

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(self.output_path, fourcc, fps, (width, height))

        start_time = datetime.now()
        total_frames = int(fps * self.duration_seconds)
        frame_count = 0

        try:
            while self.is_recording and frame_count < total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
                frame_count += 1
                
                # Emit progress every second
                if frame_count % int(fps) == 0:
                    elapsed = (datetime.now() - start_time).seconds
                    remaining = max(self.duration_seconds - elapsed, 0)
                    self.progress.emit(remaining)
        finally:
            cap.release()
            out.release()

        self.finished_recording.emit(self.output_path)

    def stop(self):
        self.is_recording = False

class CameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MEGAPIXEL USB Camera Control")
        self.setFixedSize(520, 400)

        self.selected_camera_index = None
        self.camera_ready = False
        self.video_length = 120
        self.recorder_thread = None

        self._build_ui()
        self._update_start_button_state()

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Camera Selection
        cam_group = QGroupBox("Camera Selection")
        cam_layout = QHBoxLayout()
        cam_layout.addWidget(QLabel("Select Camera:"))
        
        self.camera_combo = QComboBox()
        self.camera_combo.setFixedWidth(200)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_selected)
        cam_layout.addWidget(self.camera_combo)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_cameras)
        cam_layout.addWidget(self.refresh_btn)
        
        self.camera_status_label = QLabel("")
        self.camera_status_label.setFixedWidth(60)
        cam_layout.addWidget(self.camera_status_label)
        
        cam_group.setLayout(cam_layout)
        layout.addWidget(cam_group)

        # Video Length
        len_group = QGroupBox("Video Length")
        len_layout = QHBoxLayout()
        len_layout.addWidget(QLabel("Duration (seconds):"))
        
        self.length_scale = QSlider(Qt.Orientation.Horizontal)
        self.length_scale.setRange(10, 600)
        self.length_scale.setValue(self.video_length)
        self.length_scale.valueChanged.connect(self._on_length_changed)
        len_layout.addWidget(self.length_scale)
        
        self.length_label = QLabel(self._format_duration(self.video_length))
        len_layout.addWidget(self.length_label)
        
        len_group.setLayout(len_layout)
        layout.addWidget(len_group)

        # Output Folder
        folder_group = QGroupBox("Output Folder")
        folder_layout = QHBoxLayout()
        
        self.folder_entry = QLineEdit()
        self.folder_entry.textChanged.connect(self._update_start_button_state)
        folder_layout.addWidget(self.folder_entry)
        
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.browse_btn)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Start / Stop
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.clicked.connect(self._toggle_recording)
        self.start_btn.setMinimumHeight(40)
        layout.addWidget(self.start_btn)
        
        layout.addStretch()

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Select a camera and output folder to begin.")

    @staticmethod
    def _format_duration(seconds):
        seconds = int(float(seconds))
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"

    def _update_start_button_state(self):
        folder = self.folder_entry.text().strip()
        ready = (
            self.camera_ready
            and folder != ""
            and os.path.isdir(folder)
        )
        self.start_btn.setEnabled(ready)

    def _refresh_cameras(self):
        self.refresh_btn.setEnabled(False)
        self.camera_combo.clear()
        self.camera_status_label.setText("")
        self.selected_camera_index = None
        self.camera_ready = False
        self._update_start_button_state()
        self.status_bar.showMessage("Scanning for cameras…")
        
        self.scanner_thread = CameraScannerThread()
        self.scanner_thread.finished.connect(self._on_cameras_scanned)
        self.scanner_thread.start()

    def _on_cameras_scanned(self, cameras):
        self.refresh_btn.setEnabled(True)
        if cameras:
            self.camera_combo.blockSignals(True)
            for i in cameras:
                self.camera_combo.addItem(f"Camera {i}", userData=i)
            self.camera_combo.setCurrentIndex(-1)
            self.camera_combo.blockSignals(False)
            self.status_bar.showMessage(f"Found {len(cameras)} camera(s).")
        else:
            self.status_bar.showMessage("No cameras found.")

    def _on_camera_selected(self, index):
        if index < 0:
            return
        cam_index = self.camera_combo.itemData(index)
        if cam_index is None:
            return
            
        self.selected_camera_index = cam_index
        self.status_bar.showMessage(f"Testing Camera {cam_index}…")
        self.camera_combo.setEnabled(False)
        
        self.tester_thread = CameraTesterThread(cam_index)
        self.tester_thread.finished.connect(self._on_camera_tested)
        self.tester_thread.start()

    def _on_camera_tested(self, index, success):
        self.camera_combo.setEnabled(True)
        if success:
            self.camera_ready = True
            self.camera_status_label.setText("ready")
            self.camera_status_label.setStyleSheet("color: green;")
            self.status_bar.showMessage(f"Camera {index} is ready.")
        else:
            self.camera_ready = False
            self.camera_status_label.setText("error")
            self.camera_status_label.setStyleSheet("color: red;")
            self.status_bar.showMessage(f"Camera {index} is not available.")
        self._update_start_button_state()

    def _on_length_changed(self, value):
        self.video_length = value
        self.length_label.setText(CameraApp._format_duration(value))

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.folder_entry.setText(path)
            self._update_start_button_state()

    def _toggle_recording(self):
        if self.recorder_thread is not None and self.recorder_thread.isRunning():
            self.recorder_thread.stop()
            self.start_btn.setEnabled(False)
            self.start_btn.setText("Stopping...")
            return

        folder = self.folder_entry.text().strip()
        if not os.path.isdir(folder):
            QMessageBox.critical(self, "Error", "The selected output folder does not exist.")
            return

        output_path = generate_video_filename(folder)
        duration = self.video_length

        self.start_btn.setText("Stop Recording")
        self.status_bar.showMessage(f"Recording to {os.path.basename(output_path)}…")

        self.recorder_thread = CameraRecorderThread(self.selected_camera_index, output_path, duration)
        self.recorder_thread.progress.connect(self._on_recording_progress)
        self.recorder_thread.error.connect(self._on_recording_error)
        self.recorder_thread.finished_recording.connect(self._on_recording_finished)
        self.recorder_thread.start()
        
        self.folder_entry.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.camera_combo.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.length_scale.setEnabled(False)

    def _on_recording_progress(self, remaining):
        self.status_bar.showMessage(f"Recording… {self._format_duration(remaining)} remaining")

    def _on_recording_error(self, err_msg):
        QMessageBox.critical(self, "Error", err_msg)
        self._reset_after_recording()

    def _on_recording_finished(self, output_path):
        self.status_bar.showMessage(f"Saved: {output_path}")
        self._reset_after_recording()

    def _reset_after_recording(self):
        self.start_btn.setText("Start Recording")
        self.start_btn.setEnabled(True)
        self.folder_entry.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.camera_combo.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.length_scale.setEnabled(True)
        self._update_start_button_state()

def main():
    app = QApplication(sys.argv)
    window = CameraApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
