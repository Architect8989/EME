import time
from runners.run_once import run


def run_batch(n=30000, delay=0.1):
    for _ in range(n):
        run()
        time.sleep(delay)


if __name__ == "__main__":
    run_batch()
