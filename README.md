# Shade Walk CS

Find the shadiest walking route across the Texas A&M campus, and the shady side of the campus bus, for any date and time.

- **Walk:** compares the shortest route with a shade-first route, using building and tree shadows computed for the sun's exact position.
- **Ride the bus:** for any Aggie Spirit route and pair of stops, tells you which side to sit on and how many fewer minutes of direct sun you get.
- Free, no sign-in, no tracking. Works offline once opened, and can be added to a phone's home screen.

Unofficial student project. Not affiliated with or endorsed by Texas A&M University or Transportation Services.

## How it works

| Piece | Source |
|---|---|
| Sun position | Solar position algorithm (after SunCalc), Central Time with daylight saving |
| Campus buildings | OpenStreetMap footprints; heights measured from USGS 3DEP lidar (2018) at 1 m |
| Trees | Meta & WRI High Resolution Canopy Height Maps v2, resampled to 2 m; crowns occupy 35–100 % of tree height |
| Walkways | OpenStreetMap footways and roads, routed with Dijkstra (sunny metres cost more) |
| Bus routes | OpenStreetMap Aggie Spirit route relations; breaks filled with the shortest road path and checked against City of College Station and TAMU bus-road layers |
| Off-campus shade | Lidar surface + canopy in a 150 m band along each route, precomputed per 12 m point for 192 sun positions |

A point is shaded when a ray toward the sun passes below a roof or through a tree crown.

## Repository layout

```
src/template.html     the app (HTML, CSS, JS) with data placeholders
data/*.json           processed data embedded at build time (ODbL, see DATA-LICENSES.md)
tools/*.py            scripts that produced data/ from the public sources
build.ps1             builds docs/ (the public site)
docs/                 the site GitHub Pages serves
```

## Build

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

`-Name "..."` sets the app name shown on the page, in the tab and on the home-screen icon.

## Deploy (GitHub Pages)

1. Push this repository to GitHub.
2. Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`.
3. The site appears at `https://<user>.github.io/<repo>/` within a minute or two.

Any static host works: upload the contents of `docs/`.

## Data and attribution

See [DATA-LICENSES.md](DATA-LICENSES.md). Map data © OpenStreetMap contributors.
