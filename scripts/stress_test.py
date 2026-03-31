import multiprocessing
import time


def stress():
    while True:
        pass


if __name__ == "__main__":
    print("Hammering CPU for demo...")
    processes = [
        multiprocessing.Process(target=stress)
        for _ in range(multiprocessing.cpu_count())
    ]
    for p in processes:
        p.start()

    time.sleep(30)
    for p in processes:
        p.terminate()
