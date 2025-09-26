# Extract Curves and Centroids (QGIS Processing Script)

## 📌 Description
This QGIS Processing script **extracts curve segments from a densified line layer**, calculates their radius of curvature, optionally groups nearby curve centers, and produces up to **two output layers**:

**Resulting curves and centroids:**  
![Example output](https://github.com/Javisionario/Radios-de-curva/blob/images/Ejemplo.png)

- **Curves layer**  
  Each feature represents a curve segment with attributes:  
  - `ID_Curva`: unique ID for the curve segment  
  - `ID_Centroide`: ID of the cluster centroid the curve belongs to (or `-1` if not applicable)  
  - `Radio`: curvature radius (m)  
  - `Longitud`: segment length (m)

- **Centroids layer** *(optional)*  
  Each feature represents a cluster of nearby curve centers, with attributes:  
  - `ID_Centroide`: unique cluster ID  
  - `Radio_medio`: mean radius of all curves in the cluster (m)  
  - `Conteo`: number of curves in the cluster  

---

## ⚙️ Parameters
- **Input line layer**: Vector line layer to be analyzed.  
- **Densification interval (m)**: Distance between added vertices when densifying lines (default: `15.0`).  
- **Minimum radius (m)**: Exclude curves tighter than this threshold (default: `2.0`).  
- **Maximum radius (m)**: Exclude curves flatter than this threshold (default: `50.0`).  
- **Minimum distance between vertices (m)**: Skip triplets where vertices are too close (default: `0.5`).  
- **Generate centroid layer (boolean)**: If enabled, produces a second point layer with curve centers (default: `False`).  
- **Cluster distance (m)**: Maximum distance for grouping curve centers into the same cluster (default: `10.0`).

**Script window:**  
![Script window](https://github.com/Javisionario/Radios-de-curva/blob/images/Ventana.png)

---

## 📊 Methodology
The script analyzes every triplet of consecutive vertices `(p1, p2, p3)` in the densified line layer:

1. Compute edge lengths:  
   - `a = dist(p1, p2)`  
   - `b = dist(p2, p3)`  
   - `c = dist(p3, p1)`

2. Compute semi-perimeter:  
   - `s = (a + b + c) / 2`

3. Compute area using Heron’s formula:  
   - `area = sqrt(s(s−a)(s−b)(s−c))`

4. Compute circumcircle radius:  
   - `R = (a·b·c) / (4·area)`  

   ⚠️ If points are nearly collinear (`area ≈ 0`), no radius is calculated.  

If enabled, curve centers are also computed and then clustered based on proximity.  

---

## 🚀 Installation
1. Save the script file (e.g., `extraer_curvas_centroides.py`).  
2. In QGIS:  
   - Open **Processing Toolbox → Scripts → Add Script to Toolbox**.  
   - Load the script into your QGIS environment.  

📸 Example of the installation step:  
![Installation screenshot](https://github.com/Javisionario/Radios-de-curva/blob/images/instalar_script.png)

3. The algorithm will appear at your Processing Toolbox under the group: **Script → Analisis de linea → Extraer curvas y centroides**.  

---

## ✅ Typical Use Cases
- Road safety studies: detecting tight bends.  
- Geometric road design checks.  
- Mapping and categorizing curvature for line-based infrastructures.  

---

## ❓ Frequently Asked Questions (FAQ)

**Q: Why are some curves missing in the output?**  
- They might not fall within the specified min/max radius range.  
- Triplets of points too close together may be skipped due to the minimum distance filter.  
- Collinear points do not produce a valid radius.  

**Q: Why do I get an empty centroid layer?**  
- Ensure the "Generate centroid layer" option is enabled.  
- Curves must have valid centers to form clusters.  

**Q: What CRS should I use?**  
- Use a projected coordinate system (e.g., UTM) where distances are measured in meters. Using geographic CRS (lat/long) will give incorrect results.  

**Q: Can I adjust how many vertices are generated?**  
- Yes, by changing the densification interval. Smaller values create more vertices and higher precision, but increase computation time.  

---

## ⚠️ Limitations
- The algorithm assumes reasonably clean line geometries; noisy data may produce many false curves.  
- Results depend heavily on the chosen densification interval. Too coarse → missed curves; too fine → excessive computation.  
- The clustering method is purely distance-based; it does not account for curve orientation or road context.  
- Nearly collinear triplets of points cannot generate valid radii (they are skipped).  
- Designed for projected CRS in meters — using geographic CRS (lat/long) could give meaningless distances.  

---

## 📄 License
This project is released under the **GNU General Public License v3.0**. Feel free to use, modify, and share.  
