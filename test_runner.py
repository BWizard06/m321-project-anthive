import threading
import subprocess
from time import sleep

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def main():
    discovery_thread = threading.Thread(
        target=run_script, args=('', './discovery/discovery_service.py',)
    )
    discovery_thread.start()

    hive01_thread = threading.Thread(
        target=run_script, args=('', './hives/hive1.py',)
    )
    sleep(1)
    hive01_thread.start()

    game_thread = threading.Thread(
        target=run_script, args=('', './game/game_service.py',)
    )
    sleep(1)
    game_thread.start()


    discovery_thread.join(timeout=60)
    hive01_thread.join(timeout=60)
    game_thread.join(timeout=60)

    print("All scripts have finished executing.")

def run_script(script_path, script_name):
    interpreter = './.venv/bin/python3.12'
    script = script_path + '/' + script_name
    subprocess.run([interpreter, script_name])

if __name__ == '__main__':
    main()