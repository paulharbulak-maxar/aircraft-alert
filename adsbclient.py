import multiprocessing as mp
import os
import sys
import time

import geopy.distance
import pyModeS as pms

from pyModeS.extra.tcpclient import TcpClient
from terminaltables import AsciiTable

MIN_DIST = float(os.environ.get("MIN_DIST", 5))
REF_LAT_LON = os.environ.get("REF_LAT_LON", "40.569143,-80.26556")
REF_LOC = [float(coord.strip()) for coord in REF_LAT_LON.split(",")]
print(f"Using reference location {REF_LOC} with minimum alert distance of {MIN_DIST}.")

HEADERS = ("Call", "Man", "Model", "Speed", "Rate", "Lat", "Lon", "Dist", "Alt", "Last")
ALERT_HEADERS = ("Time", "Callsign", "Manufacturer", "Model", "Distance")

# cols = { 
#     "_id" : ObjectId("63320d967d3caea1a28afc66"), 
#     "icao24" : "ac9d5c", 
#     "registration" : "N9114X", 
#     "manufacturericao" : "", 
#     "manufacturername" : "Cessna", 
#     "model" : "182D", 
#     "typecode" : "", 
#     "serialnumber" : NumberLong(18253514), 
#     "linenumber" : "", 
#     "icaoaircrafttype" : "", 
#     "operator" : "", 
#     "operatorcallsign" : "", 
#     "operatoricao" : "", 
#     "operatoriata" : "", 
#     "owner" : "Dk1 Aviation Llc", 
#     "testreg" : "", 
#     "registered" : "", 
#     "reguntil" : "2026-01-31", 
#     "status" : "", 
#     "built" : "1961-01-01", 
#     "firstflightdate" : "", 
#     "seatconfiguration" : "", 
#     "engines" : "CONT MOTOR O-470 SERIES", 
#     "modes" : "false", 
#     "adsb" : "false", 
#     "acars" : "false", 
#     "notes" : "", 
#     "categoryDescription" : "Light (< 15500 lbs)" 
# }

# define your custom class by extending the TcpClient
#   - implement your handle_messages() methods
class ADSBClient(TcpClient):
    def __init__(self, host, port, rawtype, aircraft_db=None, show_table=False, alerter=None):
        super(ADSBClient, self).__init__(host, port, rawtype)
        self.aircraft = {}
        self.show_table = show_table
        if aircraft_db is not None:
            self.aircraft_db = aircraft_db
        else:
            self.aircraft_db = None

        if alerter:
            self.alerter = alerter
        else:
            self.alerter = None

    def handle_messages(self, messages):
        msg0 = None
        msg1 = None

        for msg, ts in messages:
            if len(msg) != 28:  # wrong data length
                continue

            df = pms.df(msg)

            if df != 17:  # not ADSB
                continue

            if pms.crc(msg) != 0:  # CRC fail
                continue

            icao = pms.adsb.icao(msg)
            tc = pms.adsb.typecode(msg)

            # Typecode 5-8 (surface), 9-18 (airborne, barometric height), and 20-22 (airborne, GNSS height)
            # pms.adsb.position(msg_even, msg_odd, t_even, t_odd, lat_ref=None, lon_ref=None)
            # pms.adsb.airborne_position(msg_even, msg_odd, t_even, t_odd)
            # pms.adsb.surface_position(msg_even, msg_odd, t_even, t_odd, lat_ref, lon_ref)
            # vel = pms.adsb.surface_velocity(msg)

            # pos = pms.adsb.position_with_ref(msg, lat_ref, lon_ref)
            # pms.adsb.airborne_position_with_ref(msg, lat_ref, lon_ref)
            # pms.adsb.surface_position_with_ref(msg, lat_ref, lon_ref)

            # alt = pms.adsb.altitude(msg)

            # Typecode: 19
            # vel = pms.adsb.velocity(msg)          # Handles both surface & airborne messages
            # head = pms.adsb.speed_heading(msg)     # Handles both surface & airborne messages
            # vel = pms.adsb.airborne_velocity(msg)
            if self.aircraft.get(icao):
                ac = self.aircraft[icao]
                ts_1 = ac["ts"]
                if ts - ts_1 > 20:
                    self.aircraft.pop(icao)
                    continue
                else:
                    ac["ts"] = ts
                    ac["last"] = round(ts - ts_1, 1)
            else:
                manu = None
                model = None
                if self.aircraft_db is not None:
                    for x in self.aircraft_db.find(
                        { "icao24": icao.lower() },
                        { "_id": 0, "manufacturername": 1, "model": 1 }
                    ):
                        # print(x)
                        manu = x.get("manufacturername")
                        model = x.get("model")

                ac = {
                    "call": None,
                    "manu": manu,
                    "model": model,
                    "speed": None,
                    "rate": None,
                    "lat": None,
                    "lon": None,
                    "dist": None,
                    "alt": None,
                    "ts": ts,
                    "last": None,
                }

                self.aircraft[icao] = ac

            if 1 <= tc <= 4:
                cat = pms.adsb.category(msg)
                call = pms.adsb.callsign(msg)
                ac["call"] = call.replace("_", "")
                # print(icao, call)
            if tc == 19:
                vel = pms.adsb.velocity(msg)
                speed = vel[0]
                head = vel[1]
                vert = vel[2]
                spd_type = vel[3]
                ac["speed"] = speed
                ac["rate"] = vert
                # print(icao, speed, head, vert, spd_type)
            if 5 <= tc <= 18:
                if pms.adsb.oe_flag(msg):
                    msg1 = msg
                    t1 = ts
                else:
                    msg0 = msg
                    t0 = ts

                if msg0 and msg1:
                    pos = pms.adsb.position_with_ref(msg, REF_LOC[0], REF_LOC[1])
                    # pos = pms.adsb.position(msg0, msg1, t0, t1)
                    alt = pms.adsb.altitude(msg)
                    dist = geopy.distance.geodesic(REF_LOC, pos).miles
                    ac["lat"] = pos[0]
                    ac["lon"] = pos[1]
                    ac["dist"] = round(dist, 1)
                    ac["alt"] = alt
                    # print(icao, pos, alt)

            # date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))

            if self.show_table:
                # os.system("clear")
                table_data = [list(HEADERS)]
                table_data.extend([[v2 for k2, v2 in v.items() if k2 != "ts"] for k, v in self.aircraft.items()])
                table = AsciiTable(table_data)
                print(table.table)

            # TODO: Convert all print statements to logging messages

            # If distance is within distance threshold, process aircraft alert
            if self.alerter:
                dist = ac.get("dist")
                if dist and dist <= MIN_DIST:
                    self.alerter.process_alert(icao, ac)
                elif dist and dist > MIN_DIST and self.alerter.alerts.get(icao):
                    # TODO: Figure out how to remove aircraft that land...
                    # When aircraft goes out of range, remove from alerts
                    self.alerter.remove_alert(icao)

if __name__ == '__main__':
    # run new client, change the host, port, and rawtype if needed
    client = ADSBClient(host="127.0.0.1", port=30002, rawtype="raw", show_table=True)
    client.run()
