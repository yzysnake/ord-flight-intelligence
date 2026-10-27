"""Synthetic BTS monthly ZIP shared by the BTS staging and Dagster tests."""

import zipfile
from pathlib import Path

HEADER = [
    "Year", "Month", "DayofMonth", "FlightDate", "Reporting_Airline", "Tail_Number",
    "Flight_Number_Reporting_Airline", "OriginAirportID", "Origin", "Dest", "CRSDepTime",
    "DepTime", "DepDelay", "DepDel15", "TaxiOut", "WheelsOff", "WheelsOn", "TaxiIn",
    "CRSArrTime", "ArrTime", "ArrDelay", "Cancelled", "CancellationCode", "Diverted",
    "CRSElapsedTime", "Distance", "TotalAddGTime", "Operating_Airline ", "Duplicate",
]  # fmt: skip

ROWS = [
    # Real Aug 2026 example: DL 1209 PDX→SLC.
    ["2026", "8", "23", "2026-08-23", "DL", "N542DE", "1209", "14057", "PDX", "SLC", "1315",
     "1314", "-1.00", "0.00", "18.00", "1332", "1602", "9.00", "1607", "1611", "4.00", "0.00",
     "", "0.00", "112.00", "630.00", "", "DL", "N"],
    # Overnight: departs 23:50 CDT, arrives 02:45 PDT the next day.
    ["2026", "8", "23", "2026-08-23", "UA", "N12345", "1", "13930", "ORD", "SFO", "2350", "0010",
     "20.00", "1.00", "15.00", "0025", "0240", "5.00", "0235", "0245", "10.00", "0.00", "",
     "0.00", "285.00", "1846.00", "", "UA", "N"],
    # Cancelled: no actual times.
    ["2026", "8", "23", "2026-08-23", "AA", "N1", "2", "12953", "LGA", "ORD", "0600", "", "",
     "", "", "", "", "", "0745", "", "", "1.00", "B", "0.00", "165.00", "733.00", "", "AA", "N"],
]  # fmt: skip

ZONES = {
    "PDX": "America/Los_Angeles",
    "SLC": "America/Denver",
    "ORD": "America/Chicago",
    "SFO": "America/Los_Angeles",
    "LGA": "America/New_York",
}


def write_zip(path: Path) -> Path:
    lines = [",".join(f'"{h}"' for h in HEADER) + ","]
    lines += [",".join(f'"{v}"' if v else "" for v in row) + "," for row in ROWS]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("On_Time_test.csv", "\n".join(lines) + "\n")
        archive.writestr("readme.html", "<html></html>")
    return path
