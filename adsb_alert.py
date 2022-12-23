import requests

HEADERS = ("Call", "Man", "Model", "Speed", "Rate", "Lat", "Lon", "Dist", "Alt", "Last")
ALERT_HEADERS = ("Time", "Callsign", "Manufacturer", "Model", "Distance")


class ADSBAlert:
    def __init__(self, display_pipe=None):
        self.alerts = {}
        self.display_pipe = display_pipe
        self.display_pipe.send(["-------", "-------", 9999, None, None])
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
                self.display_pipe.send(payload)

    def remove_alert(self, icao):
        alert = self.alerts.pop(icao)
        dist = alert.get("dist")
        print(f"Removing {icao} at dist {dist}, {len(self.alerts)} alerts remain.")
        # If alert is closest, reset closest and closest_dist
        if self.closest_dist == dist:
            self.closest = None
            self.closest_dist = 9999
