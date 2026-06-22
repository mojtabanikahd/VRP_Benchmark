"""Render results/table_data.json into results/vrp_benchmark_report.docx.

One styled landscape-A4 table per VRP variant (group header row + metric sub-header
row + one row per instance), preceded by a cover page. Best (minimum) value per
comparable metric in each row is highlighted green + bold.

Run: python scripts/generate_report.py  (after scripts/aggregate.py)
"""

from __future__ import annotations

import datetime
import json
import os

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSON_PATH = os.path.join(ROOT, "results", "table_data.json")
DOCX_PATH = os.path.join(ROOT, "results", "vrp_benchmark_report.docx")

VARIANT_ORDER = ["CVRP", "VRPTW", "MDVRP", "VRPMPD", "SDVRP", "PVRP"]

# --- layout constants -----------------------------------------------------------
CONTENT_WIDTH = 15398   # DXA: A4 long edge (16838) - 2 x 720 (0.5in margins)
INST_COL_W = 900        # DXA per instance-feature column
DASH = "—"         # em-dash for null cells

# --- colours (hex, no leading #) ------------------------------------------------
C_HEADER_NAVY = "1F4E79"
C_SOLVER_BLUE = "2E75B6"
C_SUBHEAD_BLUE = "2E6DA4"
C_INST_HEAD = "2C5282"
C_ALT_ROW = "EBF3FB"
C_BEST_GREEN = "E2EFDA"
C_WHITE = "FFFFFF"
C_BODY = "000000"
C_DESC = "404040"
C_DATE = "595959"

SOLVER_LABELS = {
    "pyvrp": "PyVRP",
    "ortools": "OR-Tools",
    "vroom": "VROOM",
    "vrpsolvereasy": "VRPSolverEasy",
    "sdvrp_tabu": "Tabu Search",
    "sdvrp_pyvrp": "SDVRP-PyVRP",
    "sdvrp_ortools": "SDVRP-OR-Tools",
    "sdvrp_vroom": "SDVRP-VROOM",
    "pvrp_pyvrp": "PVRP-PyVRP",
    "pvrp_ortools": "PVRP-OR-Tools",
    "pvrp_vroom": "PVRP-VROOM",
}

METRIC_LABELS = {
    "obj": "Obj. Value",
    "gap": "Gap (%)",
    "time": "Time (s)",
    "nveh": "# Vehicles",
    "success": "Success",
}

# Metrics where a smaller value is "best" (success excluded).
COMPARABLE_METRICS = {"obj", "gap", "time", "nveh"}

VARIANT_DESCRIPTIONS = {
    "CVRP": [
        "Uchoa et al. X-set (2017); 100 instances, 101-1001 customers.",
        "Instance name encodes n (customers) and k (vehicles in BKS).",
        "Solvers: PyVRP, OR-Tools, VROOM, VRPSolverEasy (exact BCP - most cells infeasible at 10 s).",
        "Gap (%) relative to best-known solution. Lower is better for all metrics.",
    ],
    "VRPTW": [
        "Solomon benchmark; 56 instances, 100 customers each.",
        "Classes: C = clustered, R = random, RC = mixed; group 1 = narrow windows, group 2 = wide.",
        "Solvers: PyVRP, OR-Tools, VROOM, VRPSolverEasy.",
        "All runs produced errors in this experiment - success column shows 0/10.",
    ],
    "MDVRP": [
        "Cordeau benchmark; 33 instances. Old set p01-p23, new set pr01-pr10.",
        "Solvers: PyVRP, OR-Tools, VROOM. VRPSolverEasy excluded (no multi-depot support).",
        "No BKS gap reported for MDVRP.",
    ],
    "VRPMPD": [
        "Salhi-Nagy S benchmark; 70 instances (CMT01-CMT14 with H/Q/T/X/Y capacity variants).",
        "Objective is lexicographic: minimize vehicles first, then total distance.",
        "Solvers: PyVRP, OR-Tools, VROOM. No BKS gap reported.",
    ],
    "SDVRP": [
        "Cordeau type-3 benchmark; 35 instances. Old set p01-p23, new set pr01-pr12.",
        "Tabu Search is self-contained; SDVRP-PyVRP/OR-Tools/VROOM seed initial solution from base solver.",
        "Solvers: Tabu Search, SDVRP-PyVRP, SDVRP-OR-Tools, SDVRP-VROOM. No BKS gap reported.",
    ],
    "PVRP": [
        "Cordeau benchmark; 42 instances. Old set p01-p32, new set pr01-pr10.",
        "All solvers use ALNS over day-combination assignments; inner routing by base solver.",
        "Solvers: PVRP-PyVRP, PVRP-OR-Tools, PVRP-VROOM. No BKS gap reported.",
        "All runs produced errors in this experiment - success column shows 0/10.",
    ],
}

LEGEND = (
    "Bold + green = best value in row.  "
    + DASH
    + " = no successful solution found.  Success = successful runs out of 10."
)


# --- low-level oxml helpers -----------------------------------------------------

def set_cell_fill(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_width(cell, width_dxa: int):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"), str(width_dxa))
    tcW.set(qn("w:type"), "dxa")
    tcPr.insert(0, tcW)


def set_table_width(table, width_dxa: int):
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(width_dxa))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)


def set_fixed_layout(table):
    """Force fixed table layout so explicit column widths are honoured by Word."""
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)


def set_tbl_grid(table, col_widths: list[int]):
    tbl = table._tbl
    for old in tbl.findall(qn("w:tblGrid")):
        tbl.remove(old)
    tblGrid = OxmlElement("w:tblGrid")
    for w in col_widths:
        gridCol = OxmlElement("w:gridCol")
        gridCol.set(qn("w:w"), str(w))
        tblGrid.append(gridCol)
    tbl.tblPr.addnext(tblGrid)


def set_cell_borders(cell, color: str = "BFBFBF", size: int = 4):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(old)
    tcBorders = OxmlElement("w:tcBorders")
    for side in ["top", "left", "bottom", "right"]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def set_cell_margins(cell, top=60, bottom=60, left=80, right=80):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcMar")):
        tcPr.remove(old)
    tcMar = OxmlElement("w:tcMar")
    for side, val in [("top", top), ("left", left), ("bottom", bottom), ("right", right)]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        tcMar.append(el)
    tcPr.append(tcMar)


def set_cell_valign(cell, align: str = "center"):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:vAlign")):
        tcPr.remove(old)
    vAlign = OxmlElement("w:vAlign")
    vAlign.set(qn("w:val"), align)
    tcPr.append(vAlign)


# --- high-level helpers ---------------------------------------------------------

def set_landscape_a4(section):
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Mm(297)
    section.page_height = Mm(210)
    section.left_margin = section.right_margin = Inches(0.5)
    section.top_margin = section.bottom_margin = Inches(0.5)


def write_cell(cell, text, bold=False, font_size_pt=8, color_hex=C_BODY,
               align=WD_ALIGN_PARAGRAPH.CENTER):
    """Replace cell content with a single styled run."""
    p = cell.paragraphs[0]
    p.clear()
    p.alignment = align
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(font_size_pt)
    run.font.color.rgb = RGBColor.from_string(color_hex)


def style_header_cell(cell, text, fill_hex, border_hex):
    set_cell_fill(cell, fill_hex)
    set_cell_borders(cell, color=border_hex, size=6)
    set_cell_margins(cell)
    set_cell_valign(cell)
    write_cell(cell, text, bold=True, font_size_pt=9, color_hex=C_WHITE)


def calc_col_widths(n_inst_cols, n_solvers, n_metrics):
    inst_total = n_inst_cols * INST_COL_W
    remaining = CONTENT_WIDTH - inst_total
    n_solver_cells = n_solvers * n_metrics
    solver_col_w = remaining // n_solver_cells
    widths = [INST_COL_W] * n_inst_cols + [solver_col_w] * n_solver_cells
    # Push the integer-division remainder onto the last column so the grid sums
    # exactly to CONTENT_WIDTH (otherwise Word stretches the last column).
    widths[-1] += CONTENT_WIDTH - sum(widths)
    return widths


def find_best(rows, metric, solvers):
    """For each row, the set of solver keys holding the minimum value of `metric`."""
    best_per_row = []
    for row in rows:
        numeric = {
            s: row.get(f"{s}_{metric}")
            for s in solvers
            if row.get(f"{s}_{metric}") is not None
        }
        if not numeric:
            best_per_row.append(set())
        else:
            min_val = min(numeric.values())
            best_per_row.append({s for s, v in numeric.items() if v == min_val})
    return best_per_row


def fmt(value):
    return DASH if value is None else str(value)


# --- table builder --------------------------------------------------------------

def build_variant_table(doc, variant, data):
    solvers = data["solvers"]
    metrics = data["metrics"]
    inst_cols = data["inst_cols"]
    rows = data["rows"]

    n_inst = len(inst_cols)
    n_metrics = len(metrics)
    n_cols = n_inst + len(solvers) * n_metrics
    n_rows = 2 + len(rows)

    col_widths = calc_col_widths(n_inst, len(solvers), n_metrics)

    table = doc.add_table(rows=n_rows, cols=n_cols)
    table.style = "Table Grid"
    table.autofit = False
    table.allow_autofit = False
    set_table_width(table, CONTENT_WIDTH)
    set_fixed_layout(table)
    set_tbl_grid(table, col_widths)
    for r in range(n_rows):
        for c in range(n_cols):
            set_cell_width(table.cell(r, c), col_widths[c])

    # Pre-compute best cells per comparable metric.
    best = {
        m: find_best(rows, m, solvers)
        for m in metrics
        if m in COMPARABLE_METRICS
    }

    # --- Row 0: group headers ---
    merged = table.cell(0, 0).merge(table.cell(0, n_inst - 1))
    set_cell_width(merged, n_inst * INST_COL_W)
    style_header_cell(merged, "Instance Features", C_HEADER_NAVY, C_HEADER_NAVY)
    merged.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for si, solver in enumerate(solvers):
        c0 = n_inst + si * n_metrics
        c1 = c0 + n_metrics - 1
        mcell = table.cell(0, c0).merge(table.cell(0, c1))
        set_cell_width(mcell, sum(col_widths[c0:c1 + 1]))
        style_header_cell(mcell, SOLVER_LABELS.get(solver, solver),
                          C_SOLVER_BLUE, C_SOLVER_BLUE)
        mcell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # --- Row 1: metric sub-headers ---
    for ci, name in enumerate(inst_cols):
        cell = table.cell(1, ci)
        set_cell_fill(cell, C_INST_HEAD)
        set_cell_borders(cell)
        set_cell_margins(cell)
        set_cell_valign(cell)
        write_cell(cell, name, bold=True, font_size_pt=9, color_hex=C_WHITE)

    for si, solver in enumerate(solvers):
        for mi, metric in enumerate(metrics):
            cell = table.cell(1, n_inst + si * n_metrics + mi)
            set_cell_fill(cell, C_SUBHEAD_BLUE)
            set_cell_borders(cell)
            set_cell_margins(cell)
            set_cell_valign(cell)
            write_cell(cell, METRIC_LABELS.get(metric, metric),
                       bold=True, font_size_pt=9, color_hex=C_WHITE)

    # --- Data rows ---
    for ri, row in enumerate(rows):
        table_row = ri + 2
        base_fill = C_WHITE if ri % 2 == 0 else C_ALT_ROW

        for ci, name in enumerate(inst_cols):
            cell = table.cell(table_row, ci)
            set_cell_fill(cell, base_fill)
            set_cell_borders(cell)
            set_cell_margins(cell)
            set_cell_valign(cell)
            align = WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER
            write_cell(cell, fmt(row.get(name)), font_size_pt=8,
                       color_hex=C_BODY, align=align)

        for si, solver in enumerate(solvers):
            for mi, metric in enumerate(metrics):
                cell = table.cell(table_row, n_inst + si * n_metrics + mi)
                value = row.get(f"{solver}_{metric}")
                is_best = metric in best and solver in best[metric][ri]
                set_cell_fill(cell, C_BEST_GREEN if is_best else base_fill)
                set_cell_borders(cell)
                set_cell_margins(cell)
                set_cell_valign(cell)
                write_cell(cell, fmt(value), bold=is_best, font_size_pt=8,
                           color_hex=C_BODY)

    return table


# --- page composition -----------------------------------------------------------

def add_cover_page(doc):
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("VRP Solver Benchmarking Report")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor.from_string(C_HEADER_NAVY)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(
        "Comparative evaluation of solver performance across six VRP variants")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor.from_string(C_SOLVER_BLUE)

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_p.add_run(datetime.date.today().isoformat())
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor.from_string(C_DATE)

    doc.add_paragraph()

    body = doc.add_paragraph()
    run = body.add_run(
        "This report compares VRP solvers across six problem variants (CVRP, VRPTW, "
        "MDVRP, VRPMPD, SDVRP, PVRP). Each solver-instance cell was run with 10 random "
        "seeds under a 10-second wall-clock budget per run. For each cell the tables "
        "report the mean objective value, gap to best-known solution (CVRP only), "
        "runtime, vehicle count, and the number of successful runs out of 10. In every "
        "row the best (minimum) value of each comparable metric is shown in bold green; "
        "a dash (" + DASH + ") marks cells where no successful solution was found."
    )
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor.from_string(C_BODY)


def add_variant_heading(doc, variant):
    heading = doc.add_paragraph()
    run = heading.add_run(f"Table: {variant} Benchmark Results")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor.from_string(C_HEADER_NAVY)

    for line in VARIANT_DESCRIPTIONS[variant]:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        run = p.add_run(line)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string(C_DESC)

    doc.add_paragraph()  # spacer


def add_legend(doc):
    p = doc.add_paragraph()
    run = p.add_run(LEGEND)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(C_DESC)


def main():
    with open(JSON_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    doc = Document()
    add_cover_page(doc)

    for variant in VARIANT_ORDER:
        doc.add_section(WD_SECTION.NEW_PAGE)
        add_variant_heading(doc, variant)
        build_variant_table(doc, variant, data[variant])
        add_legend(doc)

    # Apply uniform landscape A4 to every section (cover + each variant page).
    for section in doc.sections:
        set_landscape_a4(section)

    doc.save(DOCX_PATH)
    print(f"Wrote {DOCX_PATH}")
    print(f"  {len(VARIANT_ORDER)} variant tables, {len(doc.sections)} sections")


if __name__ == "__main__":
    main()
