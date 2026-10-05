# Colour tables

One JSON file per colour table: `{"name", "source", "rgb"}`, where `rgb` is 256 rows of `[r, g, b]` integers 0 to 255
and `source` says where the table came from. Generated, never edited by hand:

    python3 tools/colormaps/gen_colormaps.py --json-out <this folder>

run in the HelioFITS repository (`tools/colormaps/gen_colormaps.py`, the same tables that become
`HelioFITSCore/Sources/HelioFITSCore/FITSColormaps.swift`). As generated on 2026-10-05: 79 tables, 73 from
sunpy 7.0.1, five ASPIICS tables from the SIDC page named in HelioFITS issue #9 and one EUI HRI Lyman-alpha table
from HelioFITS issue #10 (counts read from the `source` field of each file). Four file names contain a space
(`solar orbiter...`) because they keep the generator's table names.

Compare another product's tables with `../tools/diff_luts.py`. A colour table is a display choice: RHEF output is a
visualization, not a calibrated radiance.
