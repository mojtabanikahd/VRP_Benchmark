# VRP Route Studio

The web app is an interactive front end for the solvers in this repository. It has two screens:

- **Studio** builds a CVRP, VRPTW, or MDVRP scenario on a Euclidean plane, or loads a benchmark file, then solves it.
- **Fueling** is a single-depot VRPTW for refueling machines. Depots and machines sit on an OpenStreetMap, distances are real driving distances, and each solved tanker route is drawn along the streets it must drive.

The browser talks to a small FastAPI service. That service turns the scenario into a `vrpbench` instance and runs the chosen solver.

## Requirements

- Python 3.11 or newer, with this repository installed and the `web` extra (FastAPI and Uvicorn).
- Node.js 20 or newer, for the Vite frontend.
- A network connection. Studio can solve offline once the solvers are installed. Fueling loads OpenStreetMap tiles and, by default, asks the public OSRM demo server for driving distances and street geometry.

## Launch

Install the Python package from the repository root. If you already installed `vrpbench` for benchmarking, install the web extra into the same environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[web]"
```

Install the frontend once:

```powershell
cd web\app
npm install
```

Start the API and the frontend in two terminals. The API must be running before you solve; the page can open without it, but the solver list stays empty.

```powershell
# Terminal 1, from the repository root
.venv\Scripts\python.exe -m uvicorn web.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2
cd web\app
npm run dev -- --host 127.0.0.1 --port 5173
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The top bar switches between **Studio** and **Fueling**. Each screen keeps its own scenario while you switch.

Vite proxies `/api` to `http://127.0.0.1:8000`. Leave the API on that address unless you change `web/app/vite.config.ts` to match.

## Studio

Studio edits a scenario on a flat plane. Coordinates are abstract; distance is Euclidean, matching the benchmark loaders (nearest-integer for CVRP and MDVRP, raw Euclidean for VRPTW).

1. Name the scenario.
2. Choose **CVRP**, **VRPTW**, or **MDVRP**.
3. Choose a solver. CVRP and VRPTW list PyVRP, OR-Tools, VROOM, and VRPSolverEasy. MDVRP lists PyVRP, OR-Tools, and VROOM.
4. Set the vehicle capacity, the solve time budget (1–60 seconds), and the random seed. OR-Tools ignores the seed.
5. Click the plane to add a customer. Drag a point to move it. Click a point and edit it in **Inspector**, or review every point under **Nodes**.
6. Press **Delete** or **Backspace** to remove the selected customer. The last depot cannot be removed. MDVRP keeps at least two depots; use **Add depot** for more.
7. For VRPTW, set each customer's demand and time window (ready, due, and service) in the inspector.
8. Press **Solve**. The bottom dock reports the verified distance, whether the solution is feasible, and the routes. Click a route to highlight it on the plane.

**Load instance** reads a `.vrp` or `.txt` file for the variant currently selected and replaces the points on the plane.

Solve stays disabled while the scenario is incomplete: CVRP and VRPTW need exactly one depot and at least one customer, MDVRP needs at least two depots, and no customer demand may exceed the capacity. A VRPTW window must open at or before it closes.

## Fueling

Fueling is one depot and one tanker capacity. Any machine may be served by a tanker that starts and ends at that depot. The solver decides the routes.

Words used on this screen:

| On screen | Meaning |
| --- | --- |
| Machine | Equipment that needs fuel. This is a VRPTW customer. |
| Machine type | A name, a marker image, a default fuel demand in liters, and a default refueling duration in minutes. A new machine copies those two defaults. Changing a machine's type copies that type's defaults again. Editing the type later does not change machines already on the map, and each machine can still use its own fuel demand and duration. |
| Tanker | One model: a name, a tank capacity in whole liters, and the depot marker image. Every tanker in the fleet uses that capacity. |
| Depot | The single base. Its marker uses the tanker image. Tankers are not separate pins. |
| Fuel demand | Liters that machine must receive. |
| Refueling window | Clock time when fueling may start and the latest time it may start. |
| Refueling duration | Minutes the tanker spends at that machine. |
| Driving distance | Road kilometers. This is the objective. |
| Driving time | Road minutes. The refueling window is checked against this, not against the kilometers. |

### Build a scenario

1. Under **Machine types**, name each kind of machine, set **Default fuel demand (L)** and **Default refueling (min)**, and click its thumbnail to replace the image. Images must be 200 KB or smaller. New types start at 100 L and 15 minutes.
2. Under **Tanker**, set the name, tank capacity in liters, and image. That one model is the fleet.
3. Choose **PyVRP** or **OR-Tools**, then set the time budget and seed.
4. On the map, **Set depot**, **Place machine**, and **Select** sit at the top-left. Zoom in and zoom out sit at the top-right.
5. Choose **Set depot** and click once to place the depot. Drag the marker to move it. The **Details** panel sets the depot name and the shift (when tankers may leave and must return).
6. Choose **Place machine** and click the map for each machine. The new machine starts with its type's default fuel demand and refueling duration. **Details** sets the name, machine type, fuel demand in liters, refueling window, and refueling duration. **Select**, then click a marker, opens that point in **Details** without a popup. The selected marker grows slightly and gains a copper ring. Rest the pointer on a marker and its name appears beside the icon.
7. **Remove** in **Details** and on each **List** row deletes the selected depot or machine. **Delete** or **Backspace** does this too, except while typing in a field. Removing either point clears the previous routes.
8. In **List**, click a depot or machine name to select it, open its details, and move the map to it. If the map is zoomed farther out than street level, it zooms in. **Remove** on that row deletes the point and does not move the map.

Solve stays disabled until there is a depot, at least one machine, a tanker, and a solver, and every machine's fuel demand is a whole number of liters no larger than the tank.

### Save and load

**Save** downloads a `.fueling.json` file. It contains everything needed to rebuild the scenario: the name, machine types (including each default fuel demand, refueling duration, and image), the tanker, the depot and every machine with their map positions and refueling fields, plus the solver, time budget, and seed. **Load** replaces the scenario on screen and fits the map to those positions. A file saved with several tanker types keeps the one that was selected. A file saved before machine-type defaults existed loads them as 100 L and 15 minutes. An older file that omitted the solver keeps the solver, budget, and seed already on screen.

### What a solve shows

The API asks OSRM for the driving distance and driving time between the depot and every machine, solves the VRPTW, then asks OSRM for the full street geometry of each route. The map draws that geometry. It does not draw a straight line between stops. Stop numbers on the machines show the visit order. A clock label shows the interval from the tanker's arrival until it leaves, after any wait for the window and the refueling itself. Selecting one route in the dock leaves only that route's intervals on the map.

The dock reports total driving distance in kilometers, feasibility, and one card per tanker. Each card shows that trip's distance, the depot departure, each machine's arrival–departure interval, the kilometers of every hop, and the return to the depot, then the street names along that drive. Tracks with no name from the router are labeled **Unnamed roads**. Click a card to highlight that path and fit the map to it.

Moving the depot or a machine clears the previous paths, because they no longer match the positions.

A fueling scenario can include at most 99 machines. The public OSRM demo server caps a table at about 100 coordinates (the depot plus the machines) and is not meant for heavy use. To use another OSRM instance, set `OSRM_BASE_URL` in the environment of the API process before starting Uvicorn. The default is `https://router.project-osrm.org`.

## If something fails

- **The solver catalog is unavailable.** The API is not running, or it is not on port 8000. Start Uvicorn and refresh the page.
- **Solve stays disabled.** Read the notes under the left-hand controls. They name the missing depot, customer, machine, or the demand that exceeds capacity.
- **Fueling solve ends with an error about a street path.** OSRM could not return road geometry for a route. The map leaves that route undrawn rather than substituting a straight line. Check the network connection, or point `OSRM_BASE_URL` at a reachable OSRM server.
- **The map is blank in Fueling.** The browser could not load OpenStreetMap tiles. The page needs access to `tile.openstreetmap.org`.
