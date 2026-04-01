"""Unit tests for camera_app helper functions."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Ensure the module under test is importable
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__))
)

from camera_app import (
    generate_video_filename,
    get_available_cameras,
    test_camera,
    CameraApp,
)


class TestGenerateVideoFilename(unittest.TestCase):
    """Tests for generate_video_filename()."""

    def test_returns_path_inside_given_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_video_filename(tmp)
            self.assertTrue(path.startswith(tmp))

    def test_default_extension_is_avi(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_video_filename(tmp)
            self.assertTrue(path.endswith(".avi"))

    def test_custom_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_video_filename(tmp, extension=".mp4")
            self.assertTrue(path.endswith(".mp4"))

    def test_filename_contains_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            now_str = datetime.now().strftime("%Y%m%d")
            path = generate_video_filename(tmp)
            self.assertIn(now_str, os.path.basename(path))

    def test_filename_starts_with_video_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_video_filename(tmp)
            basename = os.path.basename(path)
            self.assertTrue(basename.startswith("video_"))


class TestGetAvailableCameras(unittest.TestCase):
    """Tests for get_available_cameras() with mocked cv2."""

    @patch("camera_app.cv2.VideoCapture")
    def test_returns_indices_of_opened_cameras(self, mock_cap_cls):
        """When cameras at indices 0 and 2 are available, return [0, 2]."""
        def side_effect(index):
            cap = MagicMock()
            cap.isOpened.return_value = index in (0, 2)
            return cap

        mock_cap_cls.side_effect = side_effect
        result = get_available_cameras(max_index=4)
        self.assertEqual(result, [0, 2])

    @patch("camera_app.cv2.VideoCapture")
    def test_returns_empty_when_no_cameras(self, mock_cap_cls):
        cap = MagicMock()
        cap.isOpened.return_value = False
        mock_cap_cls.return_value = cap

        result = get_available_cameras(max_index=3)
        self.assertEqual(result, [])


class TestTestCamera(unittest.TestCase):
    """Tests for test_camera() with mocked cv2."""

    @patch("camera_app.cv2.VideoCapture")
    def test_returns_true_when_frame_read(self, mock_cap_cls):
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.return_value = (True, MagicMock())
        mock_cap_cls.return_value = cap

        self.assertTrue(test_camera(0))
        cap.release.assert_called_once()

    @patch("camera_app.cv2.VideoCapture")
    def test_returns_false_when_not_opened(self, mock_cap_cls):
        cap = MagicMock()
        cap.isOpened.return_value = False
        mock_cap_cls.return_value = cap

        self.assertFalse(test_camera(0))

    @patch("camera_app.cv2.VideoCapture")
    def test_returns_false_when_read_fails(self, mock_cap_cls):
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.return_value = (False, None)
        mock_cap_cls.return_value = cap

        self.assertFalse(test_camera(0))


class TestFormatDuration(unittest.TestCase):
    """Tests for CameraApp._format_duration static method."""

    def test_two_minutes(self):
        self.assertEqual(CameraApp._format_duration(120), "02:00")

    def test_zero(self):
        self.assertEqual(CameraApp._format_duration(0), "00:00")

    def test_90_seconds(self):
        self.assertEqual(CameraApp._format_duration(90), "01:30")

    def test_float_input(self):
        self.assertEqual(CameraApp._format_duration(65.7), "01:05")

    def test_ten_minutes(self):
        self.assertEqual(CameraApp._format_duration(600), "10:00")


if __name__ == "__main__":
    unittest.main()
