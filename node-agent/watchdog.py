import psutil
import time
from typing import List

class Watchdog:
    def __init__(self, threshold=80.0, window_size=5):
        self.threshold = threshold
        self.window_size = window_size
        self.history: List[float] = []

    def get_cpu_average(self):
        usage = psutil.cpu_percent(interval=1)
        self.history.append(usage)
        if len(self.history) > self.window_size:
            self.history.pop(0)
        
        return sum(self.history) / len(self.history)

    def is_busy(self):
        avg = self.get_cpu_average()
        return avg > self.threshold

if __name__ == "__main__":
    w = Watchdog()
    while True:
        print(f"CPU Avg: {w.get_cpu_average()}% - Busy: {w.is_busy()}")
        time.sleep(1)
