# Poplar Corner Shelves Over Toilet

Two poplar shelves above the toilet that fasten to **both the back wall and the left side wall** (corner mount), not free-floating brackets alone.

## Spec

| Dimension | Value |
|---|---|
| Shelf size | **20 × 6 × 1.5 in** (each) |
| Quantity | **2** |
| Wood | Poplar |
| Clear gap between shelves | **12 in** |
| Lower shelf bottom above tank lid | **26 in** (range 24–28) |
| Horizontal alignment | **Left end tight to left wall**; back edge tight to rear wall; extends right over the toilet bay |
| Mount | Cleats/ledgers on **back wall + left wall**, screws into studs |

## Mount concept

```text
Left wall                     Rear wall
    |                              |
    |====+=========================|  ← shelf top view
    |    |        20 in            |
    | 6in|                         |
    |    |                         |
```

- **Back edge** sits on (or is screwed to) a rear-wall cleat.  
- **Left end** sits on (or is screwed to) a left-wall cleat.  
- Cleats are poplar or matching stock, ~¾ × 1½ in, painted or finished to blend.  
- Optional pin nails / finish screws down through the shelf into each cleat after leveling.

## Package contents

| Path | Purpose |
|---|---|
| [shopping-list.txt](shopping-list.txt) | Materials, hardware, finish, tools |
| [cut-list.txt](cut-list.txt) | Shelf + cleat cuts |
| [templates/wall-marking-worksheet.txt](templates/wall-marking-worksheet.txt) | Corner elevations and studs |
| [templates/milling-drill-guide.txt](templates/milling-drill-guide.txt) | Mill shelves and cleats |
| [templates/finish-schedule.txt](templates/finish-schedule.txt) | Sand and topcoat |
| [templates/install-guide.txt](templates/install-guide.txt) | Dual-wall cleat install |
| [diagrams/wall-layout.svg](diagrams/wall-layout.svg) | Elevation layout |
| [diagrams/shelf-plan.svg](diagrams/shelf-plan.svg) | Plan view — left + back attachment |
| [layout_calc.py](layout_calc.py) | Prints elevations and checklist |

## Quick layout numbers (defaults)

```bash
python3 diy/poplar-floating-shelves/layout_calc.py --tank-width 19 --checklist
```

- Left end at **left wall** (0 in from corner along back wall)  
- Right end at **20 in** from left wall along rear wall  
- Lower shelf **26.00–27.50 in** above lid  
- Upper shelf **39.50–41.00 in** above lid  
- **12 in** clear between shelves  

## Build order

1. **Measure / mark** — Corner plumb line, elevations, studs on both walls.  
2. **Mill shelves + cleats** — Two 20×6×1.5 blanks and four cleat pieces (2 back, 2 left).  
3. **Finish** — Sand and topcoat; cure fully.  
4. **Install** — Level lower cleats on both walls, set lower shelf, then upper.

## Success criteria

- Left end and back edge tight to both walls  
- Level, no wobble, load shared by both walls  
- Clear of the towel cabinet; basket clears the lower shelf  
- Sealed finish suitable for bathroom humidity  
