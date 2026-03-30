import psutil
import time
import threading
from collections import deque

class Watchdog:
    def __init__(self, threshold=80.0, window_size=5):
        self.threshold = threshold
        self.window_size = window_size
        self.history = deque(maxlen=window_size)
        self._current_avg = 0.0
        
        # Start background thread
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        while True:
            usage = psutil.cpu_percent(interval=1)
            self.history.append(usage)
            if len(self.history) > 0:
                self._current_avg = sum(self.history) / len(self.history)

    def get_cpu_average(self):
        return self._current_avg

    def is_busy(self):
        return self._current_avg > self.threshold

if __name__ == "__main__":
    w = Watchdog()
    while True:
        print(f"CPU Avg: {w.get_cpu_average()}% - Busy: {w.is_busy()}")
        time.sleep(1)
