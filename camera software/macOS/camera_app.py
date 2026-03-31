"""
MEGAPIXEL USB Camera Control GUI for macOS

A tkinter-based GUI application that controls a USB camera to record videos.
Features:
  - Dropdown to select from available cameras with availability testing
  - Slider to set video recording duration (default: 2 minutes)
  - Folder path selector with automatic filename based on date/time
  - Start button enabled only when all settings are configured
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import cv2


def get_available_cameras(max_index=10):
    """Detect available camera devices by probing video capture indices.

    Args:
        max_index: Maximum camera index to probe.

    Returns:
        List of integers representing available camera indices.
    """
    cameras = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            cameras.append(index)
            cap.release()
    return cameras


def test_camera(index):
    """Test whether a camera at the given index can capture a frame.

    Args:
        index: Camera device index.

    Returns:
        True if a frame was successfully read, False otherwise.
    """
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return False
    ret, _ = cap.read()
    cap.release()
    return ret


def generate_video_filename(folder_path, extension=".avi"):
    """Generate a video filename based on the current date and time.

    Args:
        folder_path: Directory where the file will be saved.
        extension: File extension for the video file.

    Returns:
        Full file path string.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{timestamp}{extension}"
    return os.path.join(folder_path, filename)


class CameraApp:
    """Main application class for the MEGAPIXEL USB Camera Control GUI."""

    def __init__(self, root):
        self.root = root
        self.root.title("MEGAPIXEL USB Camera Control")
        self.root.geometry("520x400")
        self.root.resizable(False, False)

        # State variables
        self.selected_camera_index = None
        self.camera_ready = False
        self.folder_path = tk.StringVar(value="")
        self.video_length = tk.IntVar(value=120)  # default 2 minutes in seconds
        self.is_recording = False

        self._build_ui()
        self._update_start_button_state()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        """Construct all GUI widgets."""
        pad = {"padx": 10, "pady": 5}

        # --- Camera Selection ---
        cam_frame = ttk.LabelFrame(self.root, text="Camera Selection")
        cam_frame.pack(fill="x", **pad)

        ttk.Label(cam_frame, text="Select Camera:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.camera_combo = ttk.Combobox(
            cam_frame, state="readonly", width=30
        )
        self.camera_combo.grid(row=0, column=1, padx=5, pady=5)
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_selected)

        self.refresh_btn = ttk.Button(
            cam_frame, text="Refresh", command=self._refresh_cameras
        )
        self.refresh_btn.grid(row=0, column=2, padx=5, pady=5)

        self.camera_status_label = ttk.Label(
            cam_frame, text="", width=10
        )
        self.camera_status_label.grid(row=0, column=3, padx=5, pady=5)

        # --- Video Length ---
        len_frame = ttk.LabelFrame(self.root, text="Video Length")
        len_frame.pack(fill="x", **pad)

        ttk.Label(len_frame, text="Duration (seconds):").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.length_scale = ttk.Scale(
            len_frame,
            from_=10,
            to=600,
            orient="horizontal",
            variable=self.video_length,
            command=self._on_length_changed,
        )
        self.length_scale.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        len_frame.columnconfigure(1, weight=1)

        self.length_label = ttk.Label(
            len_frame, text=self._format_duration(self.video_length.get())
        )
        self.length_label.grid(row=0, column=2, padx=5, pady=5)

        # --- Output Folder ---
        folder_frame = ttk.LabelFrame(self.root, text="Output Folder")
        folder_frame.pack(fill="x", **pad)

        self.folder_entry = ttk.Entry(
            folder_frame, textvariable=self.folder_path, width=40
        )
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.folder_entry.bind("<KeyRelease>", lambda _: self._update_start_button_state())
        folder_frame.columnconfigure(0, weight=1)

        self.browse_btn = ttk.Button(
            folder_frame, text="Browse…", command=self._browse_folder
        )
        self.browse_btn.grid(row=0, column=1, padx=5, pady=5)

        # --- Start / Stop ---
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(fill="x", **pad)

        self.start_btn = ttk.Button(
            ctrl_frame, text="Start Recording", command=self._toggle_recording
        )
        self.start_btn.pack(pady=10)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Select a camera and output folder to begin.")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", anchor="w"
        )
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _format_duration(seconds):
        """Return a human-readable mm:ss string."""
        seconds = int(float(seconds))
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"

    def _update_start_button_state(self):
        """Enable the Start button only when all prerequisites are met."""
        folder = self.folder_path.get().strip()
        ready = (
            self.camera_ready
            and folder != ""
            and os.path.isdir(folder)
        )
        self.start_btn.config(state="normal" if ready else "disabled")

    # ------------------------------------------------------------ callbacks
    def _refresh_cameras(self):
        """Scan for available cameras and populate the dropdown."""
        self.camera_status_label.config(text="")
        self.selected_camera_index = None
        self.camera_ready = False
        self._update_start_button_state()
        self.status_var.set("Scanning for cameras…")
        self.root.update_idletasks()

        cameras = get_available_cameras()
        if cameras:
            labels = [f"Camera {i}" for i in cameras]
            self.camera_combo["values"] = labels
            self.status_var.set(f"Found {len(cameras)} camera(s).")
        else:
            self.camera_combo["values"] = []
            self.camera_combo.set("")
            self.status_var.set("No cameras found.")

    def _on_camera_selected(self, _event=None):
        """Handle camera dropdown selection and test availability."""
        selection = self.camera_combo.get()
        if not selection:
            return

        index = int(selection.split()[-1])
        self.selected_camera_index = index
        self.status_var.set(f"Testing Camera {index}…")
        self.root.update_idletasks()

        if test_camera(index):
            self.camera_ready = True
            self.camera_status_label.config(text="ready", foreground="green")
            self.status_var.set(f"Camera {index} is ready.")
        else:
            self.camera_ready = False
            self.camera_status_label.config(text="error", foreground="red")
            self.status_var.set(f"Camera {index} is not available.")

        self._update_start_button_state()

    def _on_length_changed(self, value):
        """Update the duration label when the slider moves."""
        self.length_label.config(text=self._format_duration(value))

    def _browse_folder(self):
        """Open a folder selection dialog."""
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.folder_path.set(path)
            self._update_start_button_state()

    def _toggle_recording(self):
        """Start or stop video recording."""
        if self.is_recording:
            self.is_recording = False
            return

        folder = self.folder_path.get().strip()
        if not os.path.isdir(folder):
            messagebox.showerror("Error", "The selected output folder does not exist.")
            return

        output_path = generate_video_filename(folder)
        duration = self.video_length.get()

        self.is_recording = True
        self.start_btn.config(text="Stop Recording")
        self.status_var.set(f"Recording to {os.path.basename(output_path)}…")
        self.root.update_idletasks()

        self._record_video(output_path, duration)

    def _record_video(self, output_path, duration_seconds):
        """Capture video from the selected camera for the given duration.

        Args:
            output_path: Full path for the output video file.
            duration_seconds: Recording length in seconds.
        """
        cap = cv2.VideoCapture(self.selected_camera_index)
        if not cap.isOpened():
            messagebox.showerror("Error", "Failed to open camera.")
            self._reset_after_recording()
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # sensible default

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        start_time = datetime.now()
        total_frames = int(fps * duration_seconds)
        frame_count = 0

        try:
            while self.is_recording and frame_count < total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
                frame_count += 1

                # Periodically update the GUI so it stays responsive
                if frame_count % int(fps) == 0:
                    elapsed = (datetime.now() - start_time).seconds
                    remaining = max(duration_seconds - elapsed, 0)
                    self.status_var.set(
                        f"Recording… {self._format_duration(remaining)} remaining"
                    )
                    self.root.update()
        finally:
            cap.release()
            out.release()

        self.status_var.set(f"Saved: {output_path}")
        self._reset_after_recording()

    def _reset_after_recording(self):
        """Restore UI state after recording finishes."""
        self.is_recording = False
        self.start_btn.config(text="Start Recording")
        self._update_start_button_state()


def main():
    """Entry point for the camera control application."""
    root = tk.Tk()
    CameraApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
