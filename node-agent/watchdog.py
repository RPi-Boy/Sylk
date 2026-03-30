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

    def get_memory_usage(self):
        return psutil.virtual_memory().percent

    def is_busy(self):
        avg_cpu = self.get_cpu_average()
        mem_usage = self.get_memory_usage()
        # Busy if CPU > threshold OR RAM > 90%
        return avg_cpu > self.threshold or mem_usage > 90.0

if __name__ == "__main__":
    w = Watchdog()
    while True:
        print(f"CPU Avg: {w.get_cpu_average():.1f}% | Mem: {w.get_memory_usage()}% | Busy: {w.is_busy()}")
        time.sleep(1)
