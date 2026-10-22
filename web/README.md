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
| Machine type | A name and a marker image. Fuel demand is set on each placed machine, not on the type. |
| Tanker type | A name, a tank capacity in whole liters, and a marker image. The scenario uses one type, so every tanker has the same capacity. |
| Depot | The single base. Its marker uses the selected tanker type's image. Tankers are not separate pins. |
| Fuel demand | Liters that machine must receive. |
| Refueling window | Clock time when fueling may start and the latest time it may start. |
| Refueling duration | Minutes the tanker spends at that machine. |
| Driving distance | Road kilometers. This is the objective. |
| Driving time | Road minutes. The refueling window is checked against this, not against the kilometers. |

### Build a scenario

1. Under **Machine types**, name each kind of machine and click its thumbnail to replace the image. Images must be 200 KB or smaller.
2. Under **Tanker types**, set the name, tank capacity in liters, and image. Press **Use** on the type that should run this scenario. The fleet capacity shown under the list is that tank.
3. Choose **PyVRP** or **OR-Tools**, then set the time budget and seed.
4. On the map, choose **Set depot** and click once to place the depot. Drag the marker to move it. The popup sets the depot name and the shift (when tankers may leave and must return).
5. Choose **Place machine** and click the map for each machine. The popup sets the name, machine type, fuel demand in liters, refueling window, and refueling duration. **Select** edits an existing marker. **Delete** or **Backspace** removes the selected machine. The depot stays until you drag it.
6. The same fields are in the **Details** panel. **List** jumps to a depot or machine.

Solve stays disabled until there is a depot, at least one machine, a tanker type, and a solver, and every machine's fuel demand is a whole number of liters no larger than the tank.

### Save and load

**Save** downloads a `.fueling.json` file. It contains the scenario name, both type catalogs, their images, the selected tanker type, the depot, and every machine. **Load** reads that file back. Solver, time budget, and seed are not stored in the file.

### What a solve shows

The API asks OSRM for the driving distance and driving time between the depot and every machine, solves the VRPTW, then asks OSRM for the full street geometry of each route. The map draws that geometry. It does not draw a straight line between stops. Stop numbers on the machines show the visit order.

The dock reports driving distance in kilometers, feasibility, and one row per tanker. Each row lists the machine order and the street names along that drive. Tracks with no name from the router are labeled **Unnamed roads**. Click a row to highlight that path and fit the map to it.

Moving the depot or a machine clears the previous paths, because they no longer match the positions.

A fueling scenario can include at most 99 machines. The public OSRM demo server caps a table at about 100 coordinates (the depot plus the machines) and is not meant for heavy use. To use another OSRM instance, set `OSRM_BASE_URL` in the environment of the API process before starting Uvicorn. The default is `https://router.project-osrm.org`.

## If something fails

- **The solver catalog is unavailable.** The API is not running, or it is not on port 8000. Start Uvicorn and refresh the page.
- **Solve stays disabled.** Read the notes under the left-hand controls. They name the missing depot, customer, machine, or the demand that exceeds capacity.
- **Fueling solve ends with an error about a street path.** OSRM could not return road geometry for a route. The map leaves that route undrawn rather than substituting a straight line. Check the network connection, or point `OSRM_BASE_URL` at a reachable OSRM server.
- **The map is blank in Fueling.** The browser could not load OpenStreetMap tiles. The page needs access to `tile.openstreetmap.org`.
