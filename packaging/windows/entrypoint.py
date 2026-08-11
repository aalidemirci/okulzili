import os
import sys
import threading

from okul_zili.app import main


if __name__ == "__main__":
    if "--tepsi-kontrol" in sys.argv:
        threading.Timer(8.0, lambda: os._exit(0)).start()
    exit_code = main()
    if any(argument.endswith("-kontrol") for argument in sys.argv[1:]):
        os._exit(exit_code)
    raise SystemExit(exit_code)
