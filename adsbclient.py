import multiprocessing as mp
import os
import sys
import time

import geopy.distance
import pyModeS as pms
import pymongo
import requests

from pyModeS.extra.tcpclient import TcpClient
from terminaltables import AsciiTable
from aircraft_display import AircraftDisplay

REF_LOC = (40.569143, -80.265560)
HEADERS = ("Call", "Man", "Model", "Speed", "Rate", "Lat", "Lon", "Dist", "Alt", "Last")
ALERT_HEADERS = ("Time", "Callsign", "Manufacturer", "Model", "Distance")
MIN_DIST = 5

myclient = pymongo.MongoClient("mongodb://mongo:mongo@192.168.1.104:27017/")
db = myclient["test"]
collection = db["aircraft"]

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
    def __init__(self, host, port, rawtype, display_pipe=None, show_table=False):
        super(ADSBClient, self).__init__(host, port, rawtype)
        self.aircraft = {}
        self.alerts = {}
        self.display_pipe = display_pipe
        self.display_pipe.send(["-------", "-------", 9999, None, None])
        self.show_table = show_table
        self.closest = None
        self.closest_dist = 9999
        self.last_alert = None

    def process_message(self, icao):
        # TODO: Send full dict to display object, don't do formatting here
        manu_model = ""
        call = self.closest.get("call")
        manu = self.closest.get("manu")
        model = self.closest.get("model")
        if manu:
            manu_model = str(manu[:3]).upper()

        if model:
            manu_model += str(model)

        dist = self.closest.get("dist")
        schd_from = self.closest.get("schd_from")
        schd_to = self.closest.get("schd_to")

        # https://api.planespotters.net/pub/photos/hex/A860B7

        # N918TA
        # If callsign is known and from/to are null, send request for flight info
        if call and (not schd_from or not schd_to):
            url = "https://www.flightradar24.com/v1/search/web/find"
            response = requests.get(url, params={"query": call, "limit": 1, "type": "live"})
            results = None
            if response.status_code == 200:
                results = response.json()["results"]
            else:
                print(response.text)
                
            # print(results)
            data = None
            if results:
                data = results[0].get("detail")

            # If results are empty or details aren't included, set to Unknown
            if data:
                schd_from = data.get("schd_from", "Unknown")
                schd_to = data.get("schd_to", "Unknown")
            else:
                schd_from = "Unknown"
                schd_to = "Unknown"

            # If it didn't just go out of range add the from/to info
            if self.alerts.get(icao):
                self.alerts[icao]["schd_from"] = schd_from
                self.alerts[icao]["schd_to"] = schd_to
            else:
                print("Not found")

        payload = [call, manu_model, dist]
        if schd_from != "Unknown" and schd_to != "Unknown":
            payload.extend([schd_from, schd_to])

        return payload

    def process_alert(self, icao, ac):
        info = { 
            "call": ac["call"], 
            "manu": ac["manu"], 
            "model": ac["model"], 
            "dist": ac["dist"]
        }
 
        alert = self.alerts.get(icao)
        if alert:
            check_vals = { k: v for k, v in alert.items() if k not in ("ts", "schd_from", "schd_to") }
        else:
            check_vals = {}

        # If key is not in alerts dict or aircraft info has been updated (besides timestamp), update record
        if not alert or check_vals != info:
            # Add timestamp after update check
            # info["ts"] = ac["ts"]
            self.alerts[icao] = info
            
            # Remove any alerts older than 1m (e.g. - ones that landed, not went out of range)
            # stale = []
            # for i, ac in self.alerts.items():
            #     if time.time() - ac["ts"] > 10:
            #         stale.append(i)
            #         if ac == self.closest:
            #             self.closest = None
            #             self.closest_dist = 9999

            # removed = [self.alerts.pop(i) for i in stale]

            # Determine closest aircraft in alerts
            for ac in self.alerts.values():
                # print(ac)
                dist = ac.get("dist")
                # Set closest aircraft and distance OR update the closest if it gets farther away
                if (dist and dist <= self.closest_dist) or (ac.get("call") == self.closest.get("call")):
                    self.closest = ac
                    self.closest_dist = dist

            # Only send message if closest has changed
            if self.display_pipe and self.closest != self.last_alert:
                self.last_alert = self.closest
                payload = self.process_message(icao)
                # print("Sending", call, manu_model, dist)
                print(f"Alerts: {len(self.alerts)}")
                self.display_pipe.send(payload)

    def remove_alert(self, icao):
        alert = self.alerts.pop(icao)
        dist = alert.get("dist")
        print(f"Removing {icao} at dist {dist}")
        # If alert is closest, reset closest and closest_dist
        if self.closest_dist == dist:
            self.closest = None
            self.closest_dist = 9999

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
                for x in collection.find(
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
            dist = ac.get("dist")
            if dist and dist <= MIN_DIST:
                self.process_alert(icao, ac)
            elif dist and dist > MIN_DIST and self.alerts.get(icao):
                # TODO: Figure out why some aircraft aren't being removed, 
                # if they're disappearing before they go out of range...
                
                # When aircraft goes out of range, remove from alerts
                self.remove_alert(icao)

if __name__ == '__main__':
    # run new client, change the host, port, and rawtype if needed
    client = ADSBClient(host="127.0.0.1", port=30002, rawtype="raw", display_pipe=parent_conn)
    client.run()
