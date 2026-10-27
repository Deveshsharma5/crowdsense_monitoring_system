"""
stream_capture.py - Low-latency video capture engine for CrowdSense.

Eliminates video stream delays caused by:
1. OpenCV internal frame buffering when processing (YOLO) takes >33ms per frame.
2. FFmpeg network packet buffering on RTSP/HTTP phone streams.
3. High stream bandwidth / TCP socket queue backpressure.
"""

import os
import sys
import time
import threading
import cv2

# Configure OpenCV / FFmpeg options for low latency on network streams:
# - rtsp_transport;tcp: prevents packet loss and corrupted frames
# - fflags;nobuffer: disables FFmpeg's internal packet queue
# - max_delay;500000: sets maximum delay to 500ms
# - flags;low_delay: decodes frames immediately without frame reordering delay
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|fflags;nobuffer|max_delay;500000|flags;low_delay"
)


class LowLatencyVideoCapture:
    """
    Threaded, zero-backlog video capture wrapper.

    Spawns a dedicated background grabber thread that continuously consumes
    frames from the camera or IP stream at native frame rate, discarding stale
    frames. When read() is called, it always returns the latest frame available,
    guaranteeing real-time video with zero buffer lag accumulation.
    """

    def __init__(self, source, width=None, height=None):
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.latest_frame = None
        self.last_frame_time = 0.0
        self.is_opened = False
        self.last_error = None

        self._open()

    def _open(self):
        src_str = str(self.source).strip()

        try:
            # DirectShow on Windows for webcam device indexes
            if isinstance(self.source, int) and os.name == "nt":
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            elif src_str.isdigit() and os.name == "nt":
                self.cap = cv2.VideoCapture(int(src_str), cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(self.source)
        except Exception as err:
            self.is_opened = False
            self.last_error = str(err)
            return False

        if not self.cap or not self.cap.isOpened():
            self.is_opened = False
            self.last_error = "Could not open video capture stream"
            return False

        self.is_opened = True

        # Configure requested dimensions if provided
        if self.width:
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.width))
            except Exception:
                pass
        if self.height:
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.height))
            except Exception:
                pass

        # Set buffer size to 1 where supported
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        # Grab first frame synchronously to verify stream is responsive
        try:
            success, frame = self.cap.read()
            if success and frame is not None:
                with self.lock:
                    self.latest_frame = frame
                    self.last_frame_time = time.time()
        except Exception:
            pass

        # Start continuous background grabber thread
        self.running = True
        self.thread = threading.Thread(
            target=self._grabber_loop,
            daemon=True,
            name=f"CaptureGrabber-{self.source}"
        )
        self.thread.start()
        return True

    def _grabber_loop(self):
        """Continuously pulls frames, always keeping the freshest frame."""
        consecutive_failures = 0
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.05)
                continue

            try:
                success, frame = self.cap.read()
                if success and frame is not None:
                    consecutive_failures = 0
                    with self.lock:
                        self.latest_frame = frame
                        self.last_frame_time = time.time()
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 60:
                        time.sleep(0.1)
                    else:
                        time.sleep(0.008)
            except Exception:
                time.sleep(0.02)

    def read(self):
        """Returns (success, frame) with the most recent live frame."""
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy()
            return False, None

    def grab_fresh(self):
        """Returns the latest frame without copying (for read-only use)."""
        with self.lock:
            return self.latest_frame

    def isOpened(self):
        if self.cap is None:
            return False
        return self.is_opened and self.cap.isOpened()

    def set(self, propId, value):
        if self.cap:
            try:
                return self.cap.set(propId, value)
            except Exception:
                pass
        return False

    def get(self, propId):
        if self.cap:
            try:
                return self.cap.get(propId)
            except Exception:
                pass
        return 0.0

    def release(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=0.6)
            except Exception:
                pass
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_opened = False
        with self.lock:
            self.latest_frame = None

