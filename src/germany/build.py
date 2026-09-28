"""Build the week across Germany, 21 to 27 September, as one map.

Rotterdam to Berlin by ICE on the Monday; three days in Berlin from a hotel on
the Hermannstrasse; by ICE to Bonn on the Thursday; Phantasialand on the
Friday; by ICE to Leipzig on the Saturday; and on the Sunday a ride round south
Leipzig, the IC to Dresden and the EC over the border to Prague. The longest
page in the set by a distance, and meant to be busy: it opens on the whole
route, and each city has a button to zoom to it.

Where each line comes from:

  gps      the two Strava recordings of Tuesday 22 September and the one of
           Sunday 27 September, in data/germany/
  osm      every rail, U-Bahn, S-Bahn, tram and bus leg, sliced out of route
           relations
  routed   the walks, and the three bicycle legs nobody recorded - Monday's
           ride to Rotterdam Centraal, Wednesday's out to Gleisdreieck, and
           Sunday's from the Nationalbibliothek back into the center of Leipzig,
           after Strava was stopped. Where the day's
           photographs fix the way, their positions are Valhalla waypoints;
           see LEGS below. Drawn dashed, so none of them passes for a recording.

    python3 src/germany/build.py        # -> germany-map.html

Some of the U-Bahn legs were not remembered, only their ends. Those are the BVG
journey planner's first suggestion between the two points, or - Thursday's -
the only route that passes where a photograph was taken; each such leg says so
in its note, and the caveat on the page repeats it.
"""
import json, math, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm import HERE, ROOT, overpass, stitch, nearest, dist, length_m, valhalla

sys.setrecursionlimit(10000)          # rdp recurses once per retained point

DATADIR = os.path.join(ROOT, "data", "germany")
OUT     = os.path.join(ROOT, "germany-map.html")
CEST    = timezone(timedelta(hours=2))    # Strava stamps UTC; the week was CEST
RDP_M   = 1.5

# ------------------------------------------------------------------ stops ---
# All public places: stations, stops, shops, restaurants, a museum, a park. The
# hotel is a business and is named in the copy, but its stop is the U-Bahn
# station 145 m away, which is where every journey from it started. The day in
# Rotterdam starts at the same tram-stop corner as the Alphen map. The two
# nights in Bonn were at a private home, so every Bonn journey starts and ends at
# the Hauptbahnhof and the last kilometer each way is not on the map. Leipzig's
# hotel is a business and is on it; Prague ends at the station.
STOPS = {
    "wilgenlei":     (51.955190, 4.472790),
    "rotterdam_cs":  (51.925057, 4.469229),
    "utrecht_cs":    (52.089431, 5.109987),
    "hilversum":     (52.226045, 5.181350),
    "berlin_hbf":    (52.524945, 13.369661),
    "suedkreuz":     (52.476572, 13.366040),
    "hermannstr":    (52.467634, 13.431241),
    "boddinstr":     (52.480168, 13.425281),
    "alexanderplatz":(52.521585, 13.413908),
    "unter_linden":  (52.516988, 13.388820),
    "gesundbrunnen": (52.549175, 13.390076),
    "flakturm":      (52.547400, 13.384200),   # Humboldthain flak tower
    "mauerpark":     (52.544500, 13.400100),
    "habba":         (52.538910, 13.409800),   # Habba Habba, Kastanienallee 15
    "eberswalder":   (52.541515, 13.412177),
    "kotti":         (52.498985, 13.418311),
    "maybachufer":   (52.493400, 13.428100),   # the Tuesday market
    "schoenlein":    (52.493055, 13.422057),
    "bundestag":     (52.520112, 13.372955),
    "hkw":           (52.519099, 13.363257),   # Haus der Kulturen der Welt
    "potsdamer":     (52.507413, 13.375119),   # where the first ride stopped
    "uniqlo":        (52.510350, 13.377810),   # Leipziger Platz 16
    "u_potsdamer":   (52.509159, 13.378215),
    "technikmuseum": (52.499200, 13.378200),
    "funkturm":      (52.507056, 13.278315),   # where the second ride stopped
    "rewe":          (52.510860, 13.291800),   # REWE City, Wundtstrasse 26
    "zait":          (52.506940, 13.301640),   # Zait & Za'atar Falafel
    "charlottenburg":(52.505048, 13.304516),
    "westkreuz":     (52.501147, 13.283036),
    "innotrans":     (52.501700, 13.271400),   # Messe Sued, the fair entrance
    "brlo":          (52.500010, 13.373610),   # BRLO Brwhouse
    "gleisdreieck":  (52.499526, 13.374032),
    "hermannplatz":  (52.486286, 13.424553),
    "mehringdamm":   (52.494131, 13.388617),
    "paradestr":     (52.478019, 13.386256),
    "sama":          (52.487330, 13.387500),   # Sama Beirut, Fidicinstrasse 43
    "luftbruecke":   (52.486084, 13.385951),
    "frankfurt_hbf": (50.107145, 8.663789),
    "siegburg":      (50.793300, 7.203140),
    "bonn_hbf":      (50.732090, 7.096980),
    "bruehl":        (50.828500, 6.911800),
    "phantasialand": (50.799800, 6.879700),   # the shuttle's stop at the gate
    "koeln_west":    (50.943100, 6.933200),
    "leipzig_hbf":   (51.345430, 12.380127),
    "ibis":          (51.342783, 12.376352),   # ibis budget, Reichsstrasse 19
    "markt":         (51.340615, 12.374581),
    "bayerischer":   (51.330200, 12.381000),
    "wlp":           (51.335438, 12.375337),
    "johannisplatz": (51.337200, 12.386800),
    "voelki":        (51.314500, 12.410500),   # Voelkerschlachtdenkmal
    "dnb":           (51.324023, 12.399432),   # where the Strava ride ended
    "rathaus":       (51.336600, 12.374800),   # Neues Rathaus
    # The north entrance on the Wiener Platz, not the middle of the train shed:
    # a point among the tracks makes the pedestrian router walk round the
    # whole station, and both Dresden walks came out 0.8 km too long.
    "dresden_hbf":   (51.041400, 13.733000),
    "frauenkirche":  (51.051900, 13.741600),
    "augustusbr":    (51.055600, 13.740000),
    "altmarkt":      (51.050300, 13.737400),
    "praha_hln":     (50.083300, 14.435300),
}
ORDER = [
    ("wilgenlei",      "Wilgenlei, Schiebroek"),
    ("rotterdam_cs",   "Rotterdam Centraal"),
    ("utrecht_cs",     "Utrecht Centraal"),
    ("hilversum",      "Hilversum"),
    ("berlin_hbf",     "Berlin Hauptbahnhof"),
    ("suedkreuz",      "Berlin Südkreuz"),
    ("hermannstr",     "S+U Hermannstraße"),
    ("boddinstr",      "U Boddinstraße, for the Homaris"),
    ("alexanderplatz", "Alexanderplatz"),
    ("unter_linden",   "U Unter den Linden"),
    ("gesundbrunnen",  "Gesundbrunnen"),
    ("flakturm",       "Humboldthain flak tower"),
    ("mauerpark",      "Mauerpark"),
    ("habba",          "Habba Habba"),
    ("eberswalder",    "U Eberswalder Straße"),
    ("kotti",          "Kottbusser Tor"),
    ("maybachufer",    "The Maybachufer market"),
    ("schoenlein",     "U Schönleinstraße"),
    ("bundestag",      "U Bundestag"),
    ("hkw",            "Haus der Kulturen der Welt"),
    ("potsdamer",      "Potsdamer Platz"),
    ("uniqlo",         "Uniqlo, Leipziger Platz"),
    ("u_potsdamer",    "U Potsdamer Platz"),
    ("technikmuseum",  "Deutsches Technikmuseum"),
    ("funkturm",       "The Funkturm and the Messe"),
    ("rewe",           "REWE, Wundtstraße"),
    ("zait",           "Zait & Za'atar"),
    ("charlottenburg", "S Charlottenburg"),
    ("westkreuz",      "S Westkreuz"),
    ("innotrans",      "InnoTrans, Messe Süd"),
    ("brlo",           "BRLO Brwhouse"),
    ("gleisdreieck",   "U Gleisdreieck"),
    ("hermannplatz",   "U Hermannplatz"),
    ("mehringdamm",    "U Mehringdamm"),
    ("paradestr",      "U Paradestraße, for Tempelhof"),
    ("sama",           "Sama Beirut"),
    ("luftbruecke",    "U Platz der Luftbrücke"),
    ("frankfurt_hbf",  "Frankfurt (Main) Hbf"),
    ("siegburg",       "Siegburg/Bonn"),
    ("bonn_hbf",       "Bonn Hauptbahnhof"),
    ("bruehl",         "Brühl"),
    ("phantasialand",  "Phantasialand"),
    ("koeln_west",     "Köln West"),
    ("leipzig_hbf",    "Leipzig Hauptbahnhof"),
    ("ibis",           "ibis budget, Reichsstraße"),
    ("markt",          "S Markt"),
    ("bayerischer",    "Bayerischer Bahnhof"),
    ("wlp",            "Wilhelm-Leuschner-Platz"),
    ("johannisplatz",  "Johannisplatz"),
    ("voelki",         "Völkerschlachtdenkmal"),
    ("dnb",            "Deutscher Platz, the Nationalbibliothek"),
    ("rathaus",        "Neues Rathaus"),
    ("dresden_hbf",    "Dresden Hauptbahnhof"),
    ("frauenkirche",   "Frauenkirche"),
    ("augustusbr",     "Augustusbrücke"),
    ("altmarkt",       "Altmarkt"),
    ("praha_hln",      "Praha hlavní nádraží"),
]
NUM  = {k: i + 1 for i, (k, _) in enumerate(ORDER)}
NAME = dict(ORDER)
NOTES = {
    "wilgenlei":     "Monday starts on this corner, by bike to the station",
    "rotterdam_cs":  "The last of Rotterdam for this trip",
    "utrecht_cs":    "A change of trains, on to Hilversum",
    "hilversum":     "Onto ICE 145, due out at 10:22, with a reserved seat and "
                     "a friend on the same train",
    "berlin_hbf":    "ICE 145 was due at 15:45 and got in about 16:10, some 25 "
                     "minutes late; it had been 35 minutes down at Spandau. "
                     "Back here on Monday evening for the S15, on Tuesday "
                     "night on the way home, and on Thursday for the ICE out",
    "suedkreuz":     "Onto the Ringbahn, 16:29",
    "hermannstr":    "The Ringbahn's stop for the hotel. One stop on the U8 "
                     "from here",
    "boddinstr":     "The station for the Homaris Tempelhofer Feld on the "
                     "Hermannstraße, 145 m away; every day started and ended here",
    "alexanderplatz":"Out of the U8 at 18:01 on Monday, and again at noon on "
                     "Tuesday",
    "unter_linden":  "Past Museumsinsel on foot, then the U5",
    "gesundbrunnen": "Off the S15, the new line north out of the Hauptbahnhof",
    "flakturm":      "The Humboldthain flak tower, 18:48 to 19:08",
    "mauerpark":     "Walked through at about 19:40",
    "habba":         "Dinner: a falafel sandwich, Kastanienallee 15",
    "eberswalder":   "Onto the U2, or so the journey planner says; the way home "
                     "is not remembered",
    "kotti":         "Tuesday starts here, 10:05, then along the Landwehrkanal "
                     "by the Urbanhafen",
    "maybachufer":   "The Tuesday and Friday market on the Neukölln bank, about "
                     "11:00",
    "schoenlein":    "Back onto the U8, north to Alexanderplatz",
    "bundestag":     "The U5 from Alexanderplatz, 12:11",
    "hkw":           "The first ride starts here, 12:46",
    "potsdamer":     "The first ride ends here, 13:16",
    "uniqlo":        "Shopping, until about 14:03",
    "u_potsdamer":   "The U2 west, at about 14:05",
    "technikmuseum": "About 14:16 to 17:00",
    "funkturm":      "The second ride ends at the Funkturm, 17:40. It is a "
                     "lift, not a climb, and it was not gone up",
    "rewe":          "A stop for groceries on the walk to dinner. Which REWE is "
                     "not recorded; this is the one on the way",
    "zait":          "Dinner: a falafel sandwich, Kaiser-Friedrich-Straße",
    "charlottenburg":"The S-Bahn along the Stadtbahn to the Hauptbahnhof, in "
                     "at 20:19",
    "westkreuz":     "The Ringbahn's stop for the Messe, and the walk from here",
    "innotrans":     "InnoTrans, all day on Wednesday, about 09:44 to 17:40",
    "brlo":          "Dinner in the Park am Gleisdreieck, about 19:45",
    "gleisdreieck":  "Off the U2 at 14:08 on Tuesday, and three minutes on the "
                     "platform filming trains. Home from here on Wednesday by "
                     "the U1 or U3 and the U8, as the journey planner has it; "
                     "that way back is not remembered",
    "hermannplatz":  "Onto the U7 west",
    "mehringdamm":   "10:56, and onto the U6 south",
    "paradestr":     "For the THF Tower and Tempelhofer Feld, from about 11:03",
    "sama":          "Lunch: a falafel sandwich, Fidicinstraße 43, about 12:15",
    "luftbruecke":   "The U6 north to Unter den Linden, then the U5",
    "frankfurt_hbf": "ICE 931 was due at 16:56 and got in 28 minutes late. "
                     "ICE 624 on was late enough out that it was still there",
    "siegburg":      "ICE 624 was due at 18:00 and ran most of an hour late; "
                     "then the Stadtbahn 66 into Bonn",
    "bonn_hbf":      "In at about 19:45 on Thursday. Friday and Saturday both "
                     "start here too; the kilometer to where the two nights were "
                     "spent is not on the map",
    "bruehl":        "Off the train at 10:19, onto the park shuttle; back here "
                     "at 18:00",
    "phantasialand": "All day, about 10:48 to 17:30",
    "koeln_west":    "18:34, then back south to Bonn",
    "leipzig_hbf":   "ICE 598 was due at 17:09; in at about 17:14. Europe's "
                     "largest station by floor area. Out again on Sunday on "
                     "IC 2441 at 15:25",
    "ibis":          "The night of the 26th",
    "markt":         "Down into the City Tunnel, just after 20:00",
    "bayerischer":   "The oldest preserved railway terminus in the world, 1842, "
                     "and the Gosebrauerei in it: 20:26 to 21:15",
    "wlp":           "Walked back past it at 21:25",
    "johannisplatz": "Onto tram 15, about 10:46",
    "voelki":        "The monument, 10:55 to about 12:15; the ride starts here",
    "dnb":           "The recorded ride ends here at 12:48; on by bike, not "
                     "recorded, at about 13:00",
    "rathaus":       "Back in the center, 13:15",
    "dresden_hbf":   "IC 2441 due 16:38. Out again after 19:32 on the EC that "
                     "was due at 19:10",
    "frauenkirche":  "The Neumarkt and the Frauenkirche",
    "augustusbr":    "The Elbe, about 18:05",
    "altmarkt":      "About 18:30, then back to the station",
    "praha_hln":     "In about 22:05. The walk to the hotel is on the Prague "
                     "itinerary, not here",
}
ARRIVE = {
    "wilgenlei": "bike",  "rotterdam_cs": "bike",  "utrecht_cs": "train",
    "hilversum": "train", "berlin_hbf": "train",   "suedkreuz": "train",
    "hermannstr": "train","boddinstr": "metro",    "alexanderplatz": "metro",
    "unter_linden": "walk","gesundbrunnen": "train","flakturm": "walk",
    "mauerpark": "walk",  "habba": "walk",         "eberswalder": "walk",
    "kotti": "metro",     "maybachufer": "walk",   "schoenlein": "walk",
    "bundestag": "metro", "hkw": "walk",           "potsdamer": "bike",
    "uniqlo": "walk",     "u_potsdamer": "walk",   "technikmuseum": "walk", "funkturm": "bike",
    "rewe": "walk",       "zait": "walk",          "charlottenburg": "walk",
    "westkreuz": "train", "innotrans": "walk",     "brlo": "bike",
    "gleisdreieck": "walk","hermannplatz": "metro","mehringdamm": "metro",
    "paradestr": "metro", "sama": "walk",          "luftbruecke": "walk",
    "frankfurt_hbf": "train", "siegburg": "train", "bonn_hbf": "tram",
    "bruehl": "train",    "phantasialand": "bus",  "koeln_west": "train",
    "leipzig_hbf": "train","ibis": "walk",         "markt": "walk",
    "bayerischer": "train","wlp": "walk",          "johannisplatz": "walk",
    "voelki": "tram",     "dnb": "bike",           "rathaus": "bike",
    "dresden_hbf": "train","frauenkirche": "walk", "augustusbr": "walk",
    "altmarkt": "walk",   "praha_hln": "train",
}
# The cities with a zoom button of their own. A leg belongs to one when both its
# ends are in it; the long-distance legs between them belong to none.
CITY = {
    "berlin": {"berlin_hbf", "suedkreuz", "hermannstr", "boddinstr",
               "alexanderplatz", "unter_linden", "gesundbrunnen", "flakturm",
               "mauerpark", "habba", "eberswalder", "kotti", "maybachufer",
               "schoenlein", "bundestag", "hkw", "potsdamer", "uniqlo",
               "u_potsdamer", "technikmuseum", "funkturm", "rewe", "zait",
               "charlottenburg", "westkreuz", "innotrans", "brlo",
               "gleisdreieck", "hermannplatz", "mehringdamm", "paradestr",
               "sama", "luftbruecke"},
    "bonn":    {"bonn_hbf", "siegburg", "bruehl", "phantasialand", "koeln_west"},
    "leipzig": {"leipzig_hbf", "ibis", "markt", "bayerischer", "wlp",
                "johannisplatz", "voelki", "dnb", "rathaus"},
    "dresden": {"dresden_hbf", "frauenkirche", "augustusbr", "altmarkt"},
}
def city_of(a, b):
    for c, keys in CITY.items():
        if a in keys and b in keys:
            return c
    return None

# -------------------------------------------------------------- relations ---
REL = {
    "ns_ic":  1323486,   # Intercity Rotterdam -> Utrecht
    "ns_4900":325839,    # Sprinter Utrecht -> Almere, by Hilversum
    "ic77":   374676,    # Amsterdam -> Berlin, which is what ICE 145 runs as
    "re5":    164793,    # RE5 Rostock -> Suedkreuz, through the tunnel
    "s41":    14981,     # Ringbahn, clockwise
    "s42":    14983,     # Ringbahn, anticlockwise
    "s15":    20982798,  # Hauptbahnhof -> Gesundbrunnen
    "s5":     2015959,   # Westkreuz -> Strausberg, the Stadtbahn eastbound
    "u8n":    2679013,   # Hermannstrasse -> Wittenau
    "u8s":    2679014,   # Wittenau -> Hermannstrasse
    "u5w":    2227744,   # Hoenow -> Hauptbahnhof
    "u2w":    2669183,   # Pankow -> Ruhleben
    "u1e":    2669205,   # Uhlandstrasse -> Warschauer Strasse
    "u7w":    2678985,   # Rudow -> Rathaus Spandau
    "u6s":    2679164,   # Alt-Tegel -> Alt-Mariendorf
    "u6n":    2679163,   # Alt-Mariendorf -> Alt-Tegel
    "ice15":  6147984,   # Binz -> Berlin -> Erfurt -> Frankfurt
    "ice49":  6124561,   # Frankfurt -> Koeln, by Siegburg/Bonn
    "str66":  34474,     # Siegburg -> Bad Honnef, by Bonn Hbf
    "str66w": 1694615,   # Bad Honnef -> Siegburg
    "re5n":   1988249,   # RE 5 Koblenz -> Emmerich, by Bonn and Bruehl
    "rb26n":  2550761,   # RB 26 Mainz -> Koeln
    "rb26s":  1988239,   # RB 26 Koeln -> Mainz
    "phl_in": 16013718,  # Phantasialand shuttle, Bruehl Bahnhof -> park
    "phl_out":16013717,  # and back
    "ice49s": 5373662,   # Koeln -> Frankfurt, by Siegburg/Bonn
    "ice11":  1797144,   # Muenchen -> Frankfurt -> Erfurt -> Leipzig -> Berlin
    "s1":     2920371,   # Leipzig S 1 through the City Tunnel, southbound
    "t15":    1185968,   # Leipzig tram 15, Miltitz -> Meusdorf
    "ic55":   380381,    # Koeln -> Leipzig -> Dresden
    "ec379":  8865697,   # Kiel -> Berlin -> Dresden -> Praha
}
RING = {"s41", "s42"}

# --------------------------------------------------------------- the legs ---
# (seq, day, kind, a, b, mode, label, note, extra). kind is "rel" (extra is the
# REL key), "walk" or "bike" (extra is a list of through-points for Valhalla),
# or "gps" (extra is the recording's file name). seq is the order of the day and
# is what the numbered key is built in; see map-common.js.
INFERRED = "Not remembered; this is the BVG journey planner's suggestion"
LEGS = [
    # Monday 21
    (10, "mon", "bike", "wilgenlei", "rotterdam_cs", "bike", "By bicycle",
     "Not recorded: Valhalla's bicycle route from the corner to the station", []),
    (20, "mon", "rel", "rotterdam_cs", "utrecht_cs", "train", "Intercity",
     "NS Intercity to Utrecht", "ns_ic"),
    (30, "mon", "rel", "utrecht_cs", "hilversum", "train", "NS train",
     "North to Hilversum, for the ICE", "ns_4900"),
    (40, "mon", "rel", "hilversum", "berlin_hbf", "train", "ICE 145",
     "Hilversum 10:22, due into Berlin at 15:45, in about 16:10. By "
     "Amersfoort, Bad Bentheim, Hannover and Wolfsburg", "ic77"),
    (50, "mon", "rel", "berlin_hbf", "suedkreuz", "train", "Regional train",
     "Down the north-south tunnel. Which regional service is not recorded; "
     "the line is the RE5's", "re5"),
    (60, "mon", "rel", "suedkreuz", "hermannstr", "train", "S42 Ringbahn",
     "Round the south of the Ring", "s42"),
    (70, "mon", "rel", "hermannstr", "boddinstr", "metro", "U8",
     "One stop north", "u8n"),
    (80, "mon", "rel", "boddinstr", "alexanderplatz", "metro", "U8",
     "Out for the evening with a friend", "u8n"),
    (90, "mon", "walk", "alexanderplatz", "unter_linden", "walk", "Walk",
     "Past the Museumsinsel", [(52.5174, 13.3974)]),
    (100, "mon", "rel", "unter_linden", "berlin_hbf", "metro", "U5",
     "The U5, under Unter den Linden to the Hauptbahnhof", "u5w"),
    (110, "mon", "rel", "berlin_hbf", "gesundbrunnen", "train", "S15",
     "The S15, the newest line in the city", "s15"),
    (120, "mon", "walk", "gesundbrunnen", "flakturm", "walk", "Walk",
     "Into the Volkspark Humboldthain", []),
    (130, "mon", "walk", "flakturm", "mauerpark", "walk", "Walk",
     "By the Blochplatz", [(52.5490, 13.3850)]),
    (140, "mon", "walk", "mauerpark", "habba", "walk", "Walk",
     "South down the park to the Kastanienallee", []),
    (150, "mon", "walk", "habba", "eberswalder", "walk", "Walk", "", []),
    (160, "mon", "rel", "eberswalder", "alexanderplatz", "metro", "U2",
     INFERRED, "u2w"),
    (170, "mon", "rel", "alexanderplatz", "boddinstr", "metro", "U8",
     INFERRED, "u8s"),
    # Tuesday 22
    (210, "tue", "rel", "boddinstr", "kotti", "metro", "U8",
     "North to Kottbusser Tor", "u8n"),
    (220, "tue", "walk", "kotti", "maybachufer", "walk", "Walk",
     "Along the Landwehrkanal by the Urbanhafen", [(52.4950, 13.4114)]),
    (230, "tue", "walk", "maybachufer", "schoenlein", "walk", "Walk", "", []),
    (240, "tue", "rel", "schoenlein", "alexanderplatz", "metro", "U8",
     "North to Alexanderplatz", "u8n"),
    (250, "tue", "rel", "alexanderplatz", "bundestag", "metro", "U5",
     "West under the Museumsinsel and Unter den Linden", "u5w"),
    (260, "tue", "walk", "bundestag", "hkw", "walk", "Walk",
     "Past the Reichstag", []),
    (270, "tue", "gps", "hkw", "potsdamer", "bike", "By bicycle",
     "Through the Tiergarten, past the Siegessaeule",
     "ride_from_Tiergarten_to_Potsdamer_Platz.gpx"),
    (280, "tue", "walk", "potsdamer", "uniqlo", "walk", "Walk",
     "Round Potsdamer Platz, below the Panoramapunkt", [(52.5085, 13.3744)]),
    # Not remembered, and first drawn as a ride. The photographs say U-Bahn:
    # Leipziger Platz at 14:04, then 14:08 exactly at U Gleisdreieck - 1.1 km
    # in four and a half minutes - and three stills and two videos within 13 m
    # of each other on the platform until 14:12. A bicycle has no reason to
    # stand on an elevated station for three minutes; a passenger filming
    # trains does.
    (285, "tue", "walk", "uniqlo", "u_potsdamer", "walk", "Walk", "", []),
    (290, "tue", "rel", "u_potsdamer", "gleisdreieck", "metro", "U2",
     "Not remembered; the photographs put it at 14:04 on Leipziger Platz and "
     "14:08 on the Gleisdreieck platform", "u2w"),
    (295, "tue", "walk", "gleisdreieck", "technikmuseum", "walk", "Walk", "", []),
    (300, "tue", "gps", "technikmuseum", "funkturm", "bike", "By bicycle",
     "West through Schoeneberg and Charlottenburg to the Messe",
     "Long_ish_city_bike_ride.gpx"),
    (310, "tue", "walk", "funkturm", "rewe", "walk", "Walk", "", []),
    (320, "tue", "walk", "rewe", "zait", "walk", "Walk",
     "Along the Kaiserdamm", [(52.5069, 13.2928)]),
    (330, "tue", "walk", "zait", "charlottenburg", "walk", "Walk", "", []),
    (340, "tue", "rel", "charlottenburg", "berlin_hbf", "train", "S-Bahn",
     "Along the Stadtbahn viaduct; the S3, S5, S7 and S9 all run it", "s5"),
    (350, "tue", "rel", "berlin_hbf", "suedkreuz", "train", "Regional train",
     "The same way home as on Monday, as far as it is remembered", "re5"),
    (360, "tue", "rel", "suedkreuz", "hermannstr", "train", "S42 Ringbahn",
     "", "s42"),
    (370, "tue", "rel", "hermannstr", "boddinstr", "metro", "U8", "", "u8n"),
    # Wednesday 23
    (410, "wed", "rel", "boddinstr", "hermannstr", "metro", "U8",
     "One stop south, for the Ring", "u8s"),
    (420, "wed", "rel", "hermannstr", "westkreuz", "train", "S41 Ringbahn",
     "Round the south and west of the Ring", "s41"),
    (430, "wed", "walk", "westkreuz", "innotrans", "walk", "Walk",
     "To the south entrance of the Messe", []),
    (440, "wed", "walk", "innotrans", "westkreuz", "walk", "Walk", "", []),
    (450, "wed", "rel", "westkreuz", "hermannstr", "train", "S42 Ringbahn",
     "", "s42"),
    (460, "wed", "rel", "hermannstr", "boddinstr", "metro", "U8", "", "u8n"),
    (470, "wed", "bike", "boddinstr", "brlo", "bike", "By bicycle",
     "Not recorded, but the photographs place it: north up the "
     "Hermannstrasse at 19:24, by the Suedstern at 19:31, into the Park am "
     "Gleisdreieck at 19:40",
     # The fourth picture, at 19:45, was taken past BRLO in the beer garden
     # side of the park; as a waypoint it adds a loop of 0.8 km, so it is
     # evidence for the time and not a point on the route.
     [(52.4861, 13.4245), (52.4898, 13.4039), (52.4920, 13.3747)]),
    (480, "wed", "walk", "brlo", "gleisdreieck", "walk", "Walk", "", []),
    (490, "wed", "rel", "gleisdreieck", "kotti", "metro", "U1",
     INFERRED, "u1e"),
    (500, "wed", "rel", "kotti", "boddinstr", "metro", "U8", INFERRED, "u8s"),
    # Thursday 24
    (610, "thu", "rel", "boddinstr", "hermannplatz", "metro", "U8",
     "Not remembered; the only way that passes Mehringdamm, where a "
     "photograph was taken at 10:56", "u8n"),
    (620, "thu", "rel", "hermannplatz", "mehringdamm", "metro", "U7",
     "Not remembered; see the U8", "u7w"),
    (630, "thu", "rel", "mehringdamm", "paradestr", "metro", "U6",
     "South under the Tempelhofer Damm", "u6s"),
    (640, "thu", "walk", "paradestr", "sama", "walk", "Walk",
     "Along the front of the old airport to Platz der Luftbruecke",
     [(52.4853, 13.3856)]),
    (650, "thu", "walk", "sama", "luftbruecke", "walk", "Walk", "", []),
    (660, "thu", "rel", "luftbruecke", "unter_linden", "metro", "U6",
     "North to Unter den Linden", "u6n"),
    (670, "thu", "rel", "unter_linden", "berlin_hbf", "metro", "U5",
     "", "u5w"),
    (680, "thu", "rel", "berlin_hbf", "frankfurt_hbf", "train", "ICE 931",
     "Out at 13:05 by Halle, Erfurt and Fulda; 28 minutes late into "
     "Frankfurt", "ice15"),
    (690, "thu", "rel", "frankfurt_hbf", "siegburg", "train", "ICE 624",
     "The high-speed line by Limburg and Montabaur, most of an hour late",
     "ice49"),
    (700, "thu", "rel", "siegburg", "bonn_hbf", "tram", "Stadtbahn 66",
     "Into Bonn, in at about 19:45", "str66"),
    # Friday 25
    (710, "fri", "rel", "bonn_hbf", "bruehl", "train", "Regional train",
     "10:06 to 10:19. The RE 5 and the RB 26 both run it; the line is the "
     "RE 5's", "re5n"),
    (720, "fri", "rel", "bruehl", "phantasialand", "bus", "Park shuttle",
     "The park's own bus from the station", "phl_in"),
    (730, "fri", "rel", "phantasialand", "bruehl", "bus", "Park shuttle",
     "Back to the station, in by 18:00", "phl_out"),
    (740, "fri", "rel", "bruehl", "koeln_west", "train", "Regional train",
     "North to Köln West, 18:34", "rb26n"),
    (750, "fri", "rel", "koeln_west", "bonn_hbf", "train", "Regional train",
     "Back south to Bonn; not in the photographs, so the time is not known",
     "rb26s"),
    # Saturday 26
    (810, "sat", "rel", "bonn_hbf", "siegburg", "tram", "Stadtbahn 66",
     "Over the Kennedybrücke at 11:42, Siegburg by 12:09", "str66w"),
    (820, "sat", "rel", "siegburg", "frankfurt_hbf", "train", "ICE 1517",
     "Due out 12:43, by Montabaur at 13:11; in about 13:55", "ice49s"),
    (830, "sat", "rel", "frankfurt_hbf", "leipzig_hbf", "train", "ICE 598",
     "Due out 14:15, by Fulda, Bad Hersfeld, Eisenach and Erfurt; into "
     "Leipzig at about 17:14", "ice11"),
    (840, "sat", "walk", "leipzig_hbf", "ibis", "walk", "Walk",
     "To the hotel", []),
    (850, "sat", "walk", "ibis", "markt", "walk", "Walk", "", []),
    (860, "sat", "rel", "markt", "bayerischer", "train", "S-Bahn",
     "Two stops south through the City Tunnel, opened 2013", "s1"),
    (870, "sat", "walk", "bayerischer", "wlp", "walk", "Walk",
     "Back north on foot", []),
    (880, "sat", "walk", "wlp", "ibis", "walk", "Walk", "", []),
    # Sunday 27
    (910, "sun", "walk", "ibis", "johannisplatz", "walk", "Walk",
     "Past the Augustusplatz", []),
    (920, "sun", "rel", "johannisplatz", "voelki", "tram", "Tram 15",
     "Not remembered; the photographs cover 2.6 km along its line in nine "
     "minutes, 10:46 to 10:55", "t15"),
    (930, "sun", "gps", "voelki", "dnb", "bike", "By bicycle",
     "South and west round the Südfriedhof and the Alte Messe",
     "Meander_around_South_Leipzig.gpx"),
    (940, "sun", "bike", "dnb", "rathaus", "bike", "By bicycle",
     "Not recorded, but the photographs place it: the Nationalbibliothek at "
     "13:00, Bayerischer Bahnhof at 13:07, the center at 13:15",
     [(51.3306, 12.3814)]),
    (950, "sun", "walk", "rathaus", "leipzig_hbf", "walk", "Walk",
     "Through the center to the station", [(51.3397, 12.3748)]),
    (960, "sun", "rel", "leipzig_hbf", "dresden_hbf", "train", "IC 2441",
     "15:25 to 16:38", "ic55"),
    (970, "sun", "walk", "dresden_hbf", "frauenkirche", "walk", "Walk",
     "Up the Prager Straße", [(51.0451, 13.7361)]),
    (980, "sun", "walk", "frauenkirche", "augustusbr", "walk", "Walk",
     "To the river", []),
    (990, "sun", "walk", "augustusbr", "altmarkt", "walk", "Walk",
     "Back by the Postplatz", [(51.0501, 13.7336)]),
    (1000, "sun", "walk", "altmarkt", "dresden_hbf", "walk", "Walk", "",
     [(51.0444, 13.7358)]),
    (1010, "sun", "rel", "dresden_hbf", "praha_hln", "train", "EC Berliner",
     "Due out 19:10 and late - still on the platform at 19:32. Up the Elbe "
     "valley and over the border at Bad Schandau; in about 22:05", "ec379"),
]
DAY = {"mon": "Monday 21", "tue": "Tuesday 22", "wed": "Wednesday 23",
       "thu": "Thursday 24", "fri": "Friday 25", "sat": "Saturday 26",
       "sun": "Sunday 27"}

# --------------------------------------------------------------- geometry ---
def read_gpx(path):
    if not os.path.exists(path):
        raise SystemExit(
            f"missing {path}\n"
            "The Strava exports are deliberately not in git. Drop the two "
            "2026-09-22 and the 2026-09-27 .gpx files back into data/germany/ "
            "to rebuild.")
    NS = "{http://www.topografix.com/GPX/1/1}"
    root = ET.parse(path).getroot()
    return [(float(p.get("lat")), float(p.get("lon")),
             datetime.strptime(p.findtext(NS + "time"), "%Y-%m-%dT%H:%M:%SZ")
             .replace(tzinfo=timezone.utc).astimezone(CEST))
            for p in root.iter(NS + "trkpt")]

def trim_loitering(pts, R=20.0):
    """Drop the standing-around at each end of a recording; see Alphen."""
    i = max(k for k in range(len(pts)) if dist(pts[0][:2], pts[k][:2]) < R
            and all(dist(pts[0][:2], q[:2]) < R for q in pts[:k + 1]))
    j = min(k for k in range(len(pts)) if dist(pts[-1][:2], pts[k][:2]) < R
            and all(dist(pts[-1][:2], q[:2]) < R for q in pts[k:]))
    return pts[i:j + 1]

def rdp(pts, eps):
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    ab = dist(a[:2], b[:2])
    far, fi = -1.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        if ab == 0:
            d = dist(p[:2], a[:2])
        else:
            ay = (a[0]-p[0])*111320.0; ax = (a[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            by = (b[0]-p[0])*111320.0; bx = (b[1]-p[1])*111320.0*math.cos(math.radians(p[0]))
            d = abs(ax*by - ay*bx) / ab
        if d > far:
            far, fi = d, i
    if far <= eps:
        return [a, b]
    return rdp(pts[:fi + 1], eps)[:-1] + rdp(pts[fi:], eps)

def rel_line(key):
    rid = REL[key]
    rel = overpass(f"[out:json][timeout:180];rel({rid});out geom;",
                   f"rel_geom_{rid}.json")["elements"][0]
    return stitch(rel)

def slice_rel(key, a, b):
    """The stretch of a route relation between two stops, in travel order.

    Both Ringbahn relations are loops, and a loop's stitched line starts
    wherever its first member happens to be. When the stop we board at comes
    after the one we leave at in that list, the way between them is the wrap
    past the end - not the reversed short stretch, which is the other direction
    round the Ring and the other line.
    """
    ln = rel_line(key)
    i, di = nearest(ln, STOPS[a])
    j, dj = nearest(ln, STOPS[b])
    if key in RING and i > j:
        seg = ln[i:] + ln[:j + 1]
    else:
        seg = ln[i:j + 1] if i <= j else list(reversed(ln[j:i + 1]))
    return seg, di, dj

# ---------------------------------------------------------------- collect ---
features = []
def add(seq, day, mode, a, b, pts, source, line, note, ride=None, km=None):
    features.append({
        "type": "Feature",
        "properties": {
            "seq": seq, "day": day, "mode": mode,
            "from": NAME[a], "to": NAME[b], "from_n": NUM[a], "to_n": NUM[b],
            "line": line,
            "km": round((km if km is not None else length_m([p[:2] for p in pts])) / 1000, 2),
            "source": source, "note": note,
            "city": city_of(a, b),
            **({"ride": ride} if ride else {}),
        },
        "geometry": {"type": "LineString",
                     "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in pts]},
    })
    p = features[-1]["properties"]
    print(f"  {seq:4d} {mode:6s} {NAME[a][:24]:26s}-> {NAME[b][:24]:26s}"
          f"{p['km']:7.2f} km {len(pts):5d} pts [{source}]")

for seq, day, kind, a, b, mode, line, note, extra in LEGS:
    if kind == "rel":
        seg, di, dj = slice_rel(extra, a, b)
        if max(di, dj) > 250:
            raise SystemExit(f"{extra} ({REL[extra]}) does not reach {a}->{b}: "
                             f"{di:.0f} m / {dj:.0f} m")
        add(seq, day, mode, a, b, seg, "osm", line, note)
    elif kind in ("walk", "bike"):
        pts = [STOPS[a]] + list(extra) + [STOPS[b]]
        costing = "pedestrian" if kind == "walk" else "bicycle"
        shape, m = valhalla(pts, costing, f"{kind}_{seq}.json")
        # A routed walk is just "walk"; a routed ride is flagged, and the page
        # draws it dashed so it cannot pass for a recording.
        add(seq, day, mode, a, b, shape, "routed", line, note, km=m)
    elif kind == "gps":
        raw = read_gpx(os.path.join(DATADIR, extra))
        pts = trim_loitering(raw)
        print(f"       {extra}: {len(raw)} fixes, {pts[0][2]:%H:%M}-"
              f"{pts[-1][2]:%H:%M}, {length_m([p[:2] for p in raw])/1000:.2f} km")
        add(seq, day, mode, a, b, rdp(pts, RDP_M), "gps", line,
            f"{pts[0][2]:%H:%M} to {pts[-1][2]:%H:%M}. {note}",
            ride=f"ride{seq}")

# ----------------------------------------------------------------- output ---
stops_fc = {"type": "FeatureCollection", "features": [
    {"type": "Feature",
     "properties": {"n": NUM[k], "name": n, "arrive": ARRIVE[k], "key": k,
                    "note": NOTES.get(k, "")},
     "geometry": {"type": "Point",
                  "coordinates": [round(STOPS[k][1], 6), round(STOPS[k][0], 6)]}}
    for k, n in ORDER]}
features.sort(key=lambda f: f["properties"]["seq"])
lines_fc = {"type": "FeatureCollection", "features": features}

tpl = open(os.path.join(HERE, "template.html")).read()
tpl = tpl.replace("__LINES__", json.dumps(lines_fc, separators=(",", ":")))
tpl = tpl.replace("__STOPS__", json.dumps(stops_fc, separators=(",", ":")))
open(OUT, "w").write(tpl)

tot = {}
for f in features:
    p = f["properties"]
    tot[p["mode"]] = tot.get(p["mode"], 0) + p["km"]
print("\ntotals: " + ", ".join(f"{k} {v:.2f} km" for k, v in sorted(tot.items())))
print(f"wrote {OUT}, {len(tpl)} bytes")
