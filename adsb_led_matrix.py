import multiprocessing as mp
import sys
import time

import pymongo

from adsb_alert import ADSBAlert
from adsbclient import ADSBClient
from aircraft_display import AircraftDisplay


def read_data_stream(display_pipe):
    ac_display = AircraftDisplay(display_pipe)
    sys.argv.extend(["-c", "2"])
    sys.argv.extend(["--led-no-drop-privs"])
    if not ac_display.process():
        ac_display.print_help()


if __name__ == "__main__":
    mp.set_start_method("spawn")
    # q = mp.Queue()
    r_conn, w_conn = mp.Pipe()
    proc = mp.Process(target=read_data_stream, args=(r_conn,))
    proc.start()

    alerter = ADSBAlert(display_pipe=w_conn)
    # run new client, change the host, port, and rawtype if needed
    mongo = pymongo.MongoClient("mongodb://mongo:mongo@192.168.1.104:27017/")
    db = mongo["test"]
    aircraft_db = db["aircraft"]

    client = ADSBClient(
        host="127.0.0.1",
        port=30002,
        rawtype="raw",
        aircraft_db=aircraft_db,
        alerter=alerter,
    )

    client.run()
    proc.join()
