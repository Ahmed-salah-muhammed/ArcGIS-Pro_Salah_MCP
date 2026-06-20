"""Build a small sample file geodatabase so you can try the Pro tools.

Run with ArcGIS Pro's python:

    "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" demos/setup_sample.py

Creates a `sample.gdb` with a `cities` point feature class (a few Egyptian
cities) you can buffer, symbolize, publish and visualize end to end.
"""
from __future__ import annotations

import os


def main(out_dir: str = "."):
    import arcpy  # only available inside ArcGIS Pro's python

    gdb = os.path.join(out_dir, "sample.gdb")
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(out_dir, "sample.gdb")

    fc = os.path.join(gdb, "cities")
    if arcpy.Exists(fc):
        arcpy.management.Delete(fc)

    sr = arcpy.SpatialReference(4326)  # WGS84
    arcpy.management.CreateFeatureclass(gdb, "cities", "POINT", spatial_reference=sr)
    arcpy.management.AddField(fc, "name", "TEXT")
    arcpy.management.AddField(fc, "population", "LONG")

    cities = [
        ("Cairo", 9_500_000, (31.2357, 30.0444)),
        ("Alexandria", 5_200_000, (29.9187, 31.2001)),
        ("Giza", 4_400_000, (31.2089, 29.9870)),
        ("Aswan", 1_500_000, (32.8998, 24.0889)),
    ]
    with arcpy.da.InsertCursor(fc, ["name", "population", "SHAPE@XY"]) as cur:
        for name, pop, xy in cities:
            cur.insertRow((name, pop, xy))

    print(f"Created {fc} with {len(cities)} cities.")


if __name__ == "__main__":
    main()
