import os
import shlex
import traceback

def debug(x):
    with open("/tmp/tttc.log", "a") as f:
        f.write(str(x) + "\n")
    os.system(f"notify-send {shlex.quote(str(x))}")

def show_stacktrace():
    a = traceback.format_exc()
    os.system(f"notify-send {shlex.quote(a)}")

def assert_environment():
    if not ("TTTC_API_ID" in os.environ or "TTTC_API_HASH" in os.environ):
        print("Please set your environment variables \"TTTC_API_ID\" and \"TTTC_API_HASH\" accordingly.")
        print("Please consult https://core.telegram.org/api/obtaining_api_id on how to get your own API id and hash.")
        exit(1)
    return os.environ["TTTC_API_ID"], os.environ["TTTC_API_HASH"]
