# LineShadowPlanner

A lightweight, Hydra-powered tool for computing tree shadow lengths and orientations over a day. Given a location, date, and tree height, it generates hourly solar positions, calculates shadow lengths and directions, and visualizes north–south vs. east–west shadow coverage.

---

## 🚀 Features

- **Solar position**  
  Computes apparent solar altitude and azimuth using pvlib.  
- **Shadow metrics**  
  Calculates shadow length (m) and direction (°) for each hour.  
- **NS/EW split**  
  Decomposes each shadow into north–south and east–west percentages.  
- **Hydra config**  
  All parameters (location, date, tree height, timezone, etc.) are YAML-configurable.  
- **Built-in plotting**  
  Generates an NS/EW shadow coverage chart for quick visualization.

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

**Default NS/EW shadow coverage**  
![NS vs EW shadow coverage](examples/flight-planner.png)

**Orientation-based flight windows**  
![Orientation planner](examples/flight-planner orientation.png)

**Light conditions for EW lines**  
![EW light shading](examples/EW_light.png)

**Light conditions for NS lines**  
![NS light shading](examples/NS_light.png)

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

