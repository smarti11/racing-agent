# Poplar Floating Shelves Over Toilet

Build package for two centered poplar floating shelves above the toilet tank, matching the approved plan.

## Spec

| Dimension | Value |
|---|---|
| Shelf size | **20 × 6 × 1.5 in** (each) |
| Quantity | **2** |
| Wood | Poplar |
| Clear gap between shelves | **12 in** |
| Lower shelf bottom above tank lid | **26 in** (range 24–28) |
| Horizontal alignment | Centered on toilet tank lid |
| Mount | Hidden floating-shelf brackets (≥ 30–50 lb each), screws into studs |

## Package contents

| Path | Purpose |
|---|---|
| [shopping-list.txt](shopping-list.txt) | Materials, hardware, finish, tools |
| [cut-list.txt](cut-list.txt) | Rough and finished cuts |
| [templates/wall-marking-worksheet.txt](templates/wall-marking-worksheet.txt) | Centerline, heights, studs |
| [templates/milling-drill-guide.txt](templates/milling-drill-guide.txt) | Mill + bracket boring |
| [templates/finish-schedule.txt](templates/finish-schedule.txt) | Sand and topcoat |
| [templates/install-guide.txt](templates/install-guide.txt) | Bracket mount and final hang |
| [diagrams/wall-layout.svg](diagrams/wall-layout.svg) | Elevation layout |
| [diagrams/shelf-drill-pattern.svg](diagrams/shelf-drill-pattern.svg) | Blank / drill schematic |
| [layout_calc.py](layout_calc.py) | Prints elevations and checklist |

## Quick layout numbers (defaults)

```bash
python3 diy/poplar-floating-shelves/layout_calc.py --tank-width 19 --checklist
```

With a 19 in tank and plan defaults:

- Ends at **±10.00 in** from tank centerline  
- Lower shelf **26.00–27.50 in** above lid  
- Upper shelf **39.50–41.00 in** above lid  
- **12 in** clear between shelves  

## Build order

1. **Measure / mark** — Complete `templates/wall-marking-worksheet.txt`; map studs.  
2. **Mill shelves** — Follow `cut-list.txt` + `templates/milling-drill-guide.txt`.  
3. **Finish** — Follow `templates/finish-schedule.txt`; cure fully.  
4. **Install** — Follow `templates/install-guide.txt`; lower bracket first, then upper.

## Success criteria

- Shelves visually centered on the tank lid  
- Level, tight to the wall, no wobble  
- Clear of the towel cabinet; basket clears the lower shelf  
- Sealed finish suitable for bathroom humidity  
