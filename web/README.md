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

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The top bar switches between **Studio** and **سوخت‌رسانی** (Fueling). Studio stays English and left-to-right. Fueling is Persian, right-to-left, and set in Vazirmatn; its map stays left-to-right so Leaflet pan and zoom keep working. Each screen keeps its own scenario while you switch.

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

Fueling is one depot and one tanker capacity. Any machine may be served by a tanker that starts and ends at that depot. The solver decides the routes. The screen is Persian and right-to-left. The names below are the labels on that screen.

| On screen | Meaning |
| --- | --- |
| ماشین | Equipment that needs fuel. This is a VRPTW customer. |
| انواع ماشین | A name, a marker image, a default fuel demand in liters (**سوخت پیش‌فرض**), and a default refueling duration in minutes (**مدت سوخت‌گیری پیش‌فرض**). A new machine copies those two defaults. Changing a machine's type copies that type's defaults again. Editing the type later does not change machines already on the map, and each machine can still use its own fuel demand and duration. |
| تانکر | One model: a name, a tank capacity in whole liters (**ظرفیت مخزن**), and the depot marker image. Every tanker in the fleet uses that capacity. |
| انبار | The single base. Its marker uses the tanker image. Tankers are not separate pins. |
| سوخت موردنیاز | Liters that machine must receive. |
| شروع پنجره / پایان پنجره | The clock interval in which the whole refueling must happen. Service starts at or after the open time and finishes at or before the close time. |
| مدت سوخت‌گیری | Minutes the tanker spends at that machine. It must fit inside that machine's window. |
| مسافت رانندگی | Road kilometers. This is the objective. |
| زمان رانندگی | Road minutes, taken from OSRM. The refueling window is checked against this, not against the kilometers. It is not shown as its own figure in the dock. |

### Build a scenario

1. Under **انواع ماشین**, name each kind of machine, set the default liters and minutes, and click its thumbnail to replace the image. Images must be 200 KB or smaller. New types start at 100 L and 15 minutes.
2. Under **تانکر**, set the name, tank capacity in liters, and image. That one model is the fleet.
3. Choose **PyVRP** or **OR-Tools**, then set **بودجهٔ زمانی** (1–60 seconds) and **بذر**.
4. On the map, **تعیین انبار**, **گذاشتن ماشین**, and **انتخاب** sit at the top-right. Zoom in and zoom out sit at the top-left.
5. Choose **تعیین انبار** and click once to place the depot. Drag the marker to move it. The **جزئیات** panel sets the depot name and the shift (**شروع شیفت** / **پایان شیفت**): when tankers may leave and must return.
6. Choose **گذاشتن ماشین** and click the map for each machine. The new machine starts with its type's default fuel demand and refueling duration, and a window of 08:00–16:00. **جزئیات** sets the name, machine type, fuel demand in liters, refueling window, and refueling duration. **انتخاب**, then click a marker, opens that point in **جزئیات** without a popup. The selected marker grows slightly and gains a copper ring. Rest the pointer on a marker and its name appears beside the icon.
7. **حذف** in **جزئیات** and on each **فهرست** row deletes the selected depot or machine. **Delete** or **Backspace** does this too, except while typing in a field. Removing either point clears the previous routes.
8. In **فهرست**, click a depot or machine name to select it, open its details, and move the map to it. If the map is zoomed farther out than street level, it zooms in. **حذف** on that row deletes the point and does not move the map.

Solve (**حل**) stays disabled until there is a depot, at least one machine, a tanker, and a solver, every machine's fuel demand is a whole number of liters no larger than the tank, and every refueling duration fits inside that machine's window. The notes under the controls name what is missing.

### Save, load, undo, and reset

**ذخیره** downloads a `.fueling.json` file. It contains everything needed to rebuild the scenario: the name, machine types (including each default fuel demand, refueling duration, and image), the tanker, the depot and every machine with their map positions and refueling fields, plus the solver, time budget, and seed. **بارگذاری** replaces the scenario on screen and fits the map to those positions. A file saved with several tanker types keeps the one that was selected. A file saved before machine-type defaults existed loads them as 100 L and 15 minutes. An older file that omitted the solver keeps the solver, budget, and seed already on screen.

**واگرد** and **ازنو** step through scenario edits: names, types, the tanker, placements, windows, loading a file, a solve, and reset. About the last 100 steps are kept. Choosing a marker, switching the map tool, and zooming are not steps. The same actions are `Ctrl+Z` and `Ctrl+Y` (or `Ctrl+Shift+Z`) while the cursor is not in a text field. **بازنشانی** returns the screen to the initial empty scenario (one machine type, one tanker, no depot, no machines, no solution) and is itself a step you can undo.

### What a solve shows

The API asks OSRM for the driving distance and driving time between the depot and every machine, solves the VRPTW, then asks OSRM for the full street geometry of each route. The map draws that geometry. It does not draw a straight line between stops. A moving dash follows each path in driving order, from the depot through the stops and back. Stop numbers on the machines show the visit order.

The clock is the refueling interval, not the moment the tanker would have arrived if it had left when the depot shift opened. Departure is delayed so the first machine is reached when its window opens, as long as every later window and the return to the depot still hold. If a later stop is still reached early, the tanker waits there, and the label shows when refueling starts and ends. Service must finish by the window's close. Selecting one route in the dock leaves only that route's intervals on the map.

The dock reports total driving distance in kilometers, whether the plan is **شدنی** or **نشدنی**, and how many tankers were used. It does not report how long the solver ran. Each card shows that trip's distance, the depot departure, each machine's refueling interval, the kilometers of every hop, and the return to the depot, then the street names along that drive. Tracks with no name from the router are labeled **خیابان‌های بدون نام**.

Click a tanker's card to draw that path in copper, dim the other paths, and fit the map to it. Click again to clear the highlight. Click a stop on the card — the depot or a machine — to fly the map to that marker and select it. The tanker's path stays highlighted.

If no route can meet the windows even by leaving the depot as early as the shift allows, the job stops with an error and draws nothing. A feasible plan is the only one drawn.

Moving the depot or a machine clears the previous paths, because they no longer match the positions.

A fueling scenario can include at most 99 machines. The public OSRM demo server caps a table at about 100 coordinates (the depot plus the machines) and is not meant for heavy use. To use another OSRM instance, set `OSRM_BASE_URL` in the environment of the API process before starting Uvicorn. The default is `https://router.project-osrm.org`.

## If something fails

- **فهرست حل‌کننده‌ها در دسترس نیست.** The API is not running, or it is not on port 8000. Start Uvicorn and refresh the page.
- **حل stays disabled.** Read the notes under the controls. They name the missing depot, customer, or machine, a demand that exceeds the tank, or a refueling duration that does not fit in its window.
- **هیچ برنامه‌ای پنجرهٔ زمانی سوخت‌گیری را رعایت نمی‌کند.** The drive cannot reach a machine inside its window, or cannot finish refueling before that window closes and still return within the depot shift. Widen the window, lengthen the depot shift, or move the point. The map does not draw that plan.
- **مسیر خیابان پیدا نشد.** OSRM could not return road geometry for a route. The map leaves that route undrawn rather than substituting a straight line. Check the network connection, or point `OSRM_BASE_URL` at a reachable OSRM server.
- **The map is blank in Fueling.** The browser could not load OpenStreetMap tiles. The page needs access to `tile.openstreetmap.org`.
