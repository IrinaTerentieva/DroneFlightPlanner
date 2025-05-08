# LineShadowPlanner

A lightweight, Hydra-powered toolkit to plan drone flights along seismic lines by minimizing tree shadows. Three flavors:

1. **Simple Time Planner** (`simple_time_planner.py`)  
   Computes NS/EW shadow percentages over a day for a single location & tree height.

2. **Orientation-Only Planner** (`orientation_planner.py`)  
   Reads a GeoPackage of line geometries, computes each line’s bearing, and finds best flight windows based on that orientation.

3. **Height & Orientation Planner** (`height_orientation_planner.py`)  
   Like the Orientation-Only Planner, but also samples a canopy-height model (CHM) around each segment to estimate tree height per segment.

---

## 🚀 Features

- **Simple Time Planner**  
  - 15-minute resolution solar positions & shadow lengths  
  - NS vs. EW shadow percentages and plotting  
  
- **Orientation-Only Planner**  
  - Bearing from North → compass category (e.g. NE, WSW)  
  - Flight windows per line geometry  
  
- **Height & Orientation Planner**  
  - Segment each line into fixed lengths  
  - Sample CHM to derive 75th percentile canopy height per segment  
  - Buffer-based shadow penetration per segment orientation  
  - Flight windows and total durations per segment  

---
## 📦 Installation

### Using conda  
```bash
conda create -n line-shadow -c conda-forge python=3.9 pvlib hydra-core matplotlib pandas numpy
conda activate line-shadow
```

### Or with pip  
```bash
pip install pvlib hydra-core matplotlib pandas numpy
```

---

## ⚙️ Configuration

In `config/config.yaml` you can set defaults for:

```yaml
hydra:
  run:
    dir: .        # write outputs in working directory

latitude:   54.938643706057285   # decimal degrees
longitude: -110.35322727751391
elevation:   800                # meters above sea level
tree_height:  10                # tree height in meters
date:       "2024-08-09"        # YYYY-MM-DD
timezone:  "America/Edmonton"
```

Override any parameter on the fly:
```bash
python src/shadow_calculator.py date=2025-04-29 tree_height=15 latitude=53.5
```

---

## ▶️ Usage

From the project root:

```bash
python src/shadow_calculator.py
```

This will print a table of hourly shadow metrics and pop up a matplotlib plot of NS/EW shadow percentages.

---

## 📂 Project Structure

```
LineShadowPlanner/
├── config/              
│   └── config.yaml      # Hydra defaults  
├── src/                 
│   └── shadow_calculator.py  
├── README.md            
└── LICENSE              # MIT License  
```

## 📊 Examples


**Light conditions for EW lines**  
![EW light shading](examples/EW_light.png)

**Light conditions for NS lines**  
![NS light shading](examples/NS_light.png)

**Orientation-based flight windows**  
![Orientation planner](examples/flight-planner orientation.png)

**Date-specific planner snapshots**  
![11 Aug snapshot](examples/flight-planner_11aug.png)  
![21 Jun snapshot](examples/flight-planner_21june.png)

---

## 🤝 Acknowledgments

Developed by:

- **Falcon & Swift Geomatics Ltd.**  
- **BERA** (Boreal Ecological Restoration Alliance)

---

## 👩‍💻 Contributors

- **Irina Terentieva** · irina.terenteva@ucalgary.ca

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](./LICENSE) for details.

