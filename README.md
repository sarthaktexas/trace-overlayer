# Fluorescence Plate Plotter

Plots fluorescence traces from a plate-viewer CSV export. One panel per scientist/date pair, one color per protein, shaded SE bands where available. Outputs a 600 dpi PNG next to the input CSV.

## Requirements

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

All Python dependencies (matplotlib, numpy, pandas) are fetched automatically on first run.

## Usage

### Command line

```bash
uv run plot_plate_fluorescence.py path/to/plate-viewer.csv
```

### macOS Quick Action (right-click a CSV in Finder)

1. Open **Automator** and create a new **Quick Action**
2. Set **Workflow receives** → `Files or Folders` in `Finder.app`
3. Add a **Run AppleScript** action and paste in the contents of `PlotFluorescence.applescript`
4. Save as `Plot Fluorescence`

Right-click any plate-viewer CSV in Finder → **Quick Actions → Plot Fluorescence**.

## CSV format

Expects plate-viewer exports with columns named:

```
<Protein> [<Scientist> · <Date>] (<Experiment>, <Well1>, <Well2>, ...)
<Protein> [<Scientist> · <Date>] (<Experiment>, <Well1>, ...) (SE)
```

The first column is treated as time (seconds).
