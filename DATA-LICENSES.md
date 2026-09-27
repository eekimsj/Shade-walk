# Data sources and licenses

The site embeds processed data from the sources below. The app shows these credits in its footer.

## OpenStreetMap — ODbL 1.0

Building footprints, walkways, roads, bus route relations and bus stop names.
© OpenStreetMap contributors, available under the Open Database License: https://www.openstreetmap.org/copyright

`data/campus.json` (footprints, walk network) and `data/bus.json` (route lines, stops) are derived databases of
OpenStreetMap and are made available under the **ODbL 1.0**. Where a mapped route had breaks, the missing stretch
was filled with the shortest path on the OpenStreetMap road network.

## High Resolution Canopy Height Maps v2 — CC BY 4.0

Tree canopy heights.
Meta and World Resources Institute (WRI) - 2026. Version 2 High Resolution Canopy Height Maps (CHMv2).
Source imagery © 2016 Vantor. https://registry.opendata.aws/dataforgood-fb-forestsv2/
License: https://creativecommons.org/licenses/by/4.0/
Changes: cropped to the campus and bus-route corridor, resampled to a 2 m grid (maximum), heights under 3 m removed.

## USGS 3D Elevation Program lidar — public domain

Building heights and off-campus obstacles, from USGS_LPC_TX_RedRiver_3Area_B2_2018_LAS_2019 (Entwine point tiles on AWS).
Courtesy of the U.S. Geological Survey. https://www.usgs.gov/3d-elevation-program

## Used for checking only (not redistributed)

- City of College Station, `bus_routes_tamu_2023` (ArcGIS Online)
- Texas A&M University, `TAMU Bus Routes` (ArcGIS Online)

Filled route gaps were compared against these layers; none of their data ships in the site.
