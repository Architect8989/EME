import time
from runners import run_once


def run_batch(n=300, delay=0.1):
    for _ in range(n):
        run_once.run()
        time.sleep(delay)


if __name__ == "__main__":
    run_batch()
