import multiprocessing as mp
import sys
import time

from adsbclient import ADSBClient
from aircraft_display import AircraftDisplay


def read_data_stream(display_pipe):
    for msg in iter(display_pipe.recv, "sentinel"):
        # print("Receiving message...")
        if len(msg) == 5:
            callsign, model, dist, schd_from, schd_to = msg
        elif len(msg) == 3:
            callsign, model, dist = msg
        else:
            raise ValueError("Unexpected number of items in response")
            
        # print(callsign, model, dist)
        if schd_from and schd_to:
            route = f"{schd_from} -> {schd_to}"
        else:
            route = None

        ac_display = AircraftDisplay(callsign, model, f"{dist}mi", route)
        sys.argv.extend(["-c", "2"])
        sys.argv.extend(["--led-no-drop-privs"])
        if (not ac_display.process()):
            ac_display.print_help()


if __name__ == '__main__':
    mp.set_start_method('spawn')
    # q = mp.Queue()
    r_conn, w_conn = mp.Pipe()
    proc = mp.Process(target=read_data_stream, args=(r_conn,))
    proc.start()

    # run new client, change the host, port, and rawtype if needed
    client = ADSBClient(host="127.0.0.1", port=30002, rawtype="raw", display_pipe=w_conn)
    client.run()

    proc.join()
