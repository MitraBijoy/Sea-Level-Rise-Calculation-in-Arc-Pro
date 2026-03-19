#todo: importing packages
import arcpy
import os
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Times New Roman"
from arcpy import env
from arcpy.sa import *
env.overwriteOutput = True

# todo: Setting up workspace and specific folders
workspace = arcpy.GetParameterAsText(0)# r"Z:\GEOG-3135\Final_Proj" #add workspace

env.workspace = workspace
InundatedRaster = arcpy.GetParameterAsText(1) #r"InundatedRaster"
InundatedPolygon = arcpy.GetParameterAsText(2)  #r"InundatedPolygon"
FinalInundatedPolygon = arcpy.GetParameterAsText(3)  #r"FinalInundatedPolygon"

if not os.path.exists(InundatedRaster):
    os.makedirs(InundatedRaster)
    print("Folder: InundatedRaster was created")
if not os.path.exists(InundatedPolygon):
    os.makedirs(InundatedPolygon)
    print("Folder: InundatedPolygon was created")
if not os.path.exists(FinalInundatedPolygon):
    os.makedirs(FinalInundatedPolygon)
    print("Folder: FinalInundatedPolygon was created")

# todo: importing the DEM and Landcover Rasters
RASTER_NAME =  arcpy.GetParameterAsText(4)# "DEM_Ctg.tif".....-> DEM dataset
LULC_NAME = arcpy.GetParameterAsText(5) # "LULC_2024_Ctg.tif"....-> LULC Dataset

input_dem = arcpy.Raster(RASTER_NAME) #import the DEM data for study area
input_lulc = arcpy.Raster(LULC_NAME) # import the Target LULC Rasters (classified)

arcpy.env.outputCoordinateSystem = arcpy.Describe(input_lulc).spatialReference

# todo: Defining the Sea Level Heights and references
scenario = arcpy.GetParameterAsText(6)#"ssp585" # For which Scenarios the SLR is measuring (e.g., SSP1-1.9, SSP2-4.5 etc...)
#height = [91, 189, 340, 522, 740, 1023, 1380, 1784, 2277, 2826, 3435, 4118, 4781, 5526] #add the sea level height based on DEM value (if DEM is in m, use m scale value)
#year = [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100, 2110, 2120, 2130, 2140, 2150] # SLR years by values

value_table_string = arcpy.GetParameterAsText(7)

height = []
year = []

if value_table_string:
    pairs = value_table_string.split(";")
    for pair in pairs:
        if pair.strip():
            year_val, height_val = pair.split(" ")
            year.append(int(float(year_val)))
            height.append(float(height_val))

#todo: LULC cover names
#lulc_names = {1: "Water Body", 2: "Vegetation", 3: "Barren", 4: "Built-up"} #update the name based on LULC

# Get LULC classes as value table (e.g., "1 Water Body;2 Vegetation;3 Barren;4 Built-up")
lulc_string = arcpy.GetParameterAsText(8)

lulc_names = {}
if lulc_string:
    pairs = lulc_string.split(";")
    for pair in pairs:
        if pair.strip():
            code, name = pair.split(" ", 1)
            lulc_names[int(code)] = name.strip()

results = []

#todo: defining a custom function that involves Raster to polygon -> Dissolve -> Add field -> Area Calculation

def raster_to_dissolved_area(in_raster_path, out_polygon_path, final_polygon_path, dissolve_field="gridcode"):

    """""
    1. Converts inundation raster to polygon for better visualization and interpretation.
    2. Dissolves pixel boundaries into a single continuous polygon representing the flood zone.
    3. Automates area calculation in sqKm for quick quantitative assessment.
    How does it works: Raster to polygon converts the inundation raster into vector format, and dissolve merges all pixel polygons into a single continuous flood polygon with calculated area.
    """""
    arcpy.conversion.RasterToPolygon(
        in_raster_path,
        out_polygon_path)

    # Dissolve
    arcpy.management.Dissolve(
        in_features=out_polygon_path,
        out_feature_class=final_polygon_path,
        dissolve_field=dissolve_field,
    )

    # Add Area field and calculate geodesic area
    arcpy.management.AddField(in_table=final_polygon_path, field_name="Area", field_type="DOUBLE")
    total_area = 0.0
    with arcpy.da.UpdateCursor(final_polygon_path, ["SHAPE@", "Area"]) as cursor:
        for row in cursor:
            area_sqkm = row[0].getArea("GEODESIC", "SQUAREKILOMETERS")
            row[1] = area_sqkm
            cursor.updateRow(row)
            total_area += area_sqkm
    return total_area

# todo: starting of the pipeline
# First calculating the low elevation pixels, removing the unnecessary pixels, convert it into polygon, and capture the potential area loss and LULC loss
for ht, ref in zip(height, year):
    arcpy.AddMessage(f"Analysis starting for the Year: {ref} where SLH is expected to be {ht} for SSP Scenario {scenario}")

    """""
    1. Automates raster calculator to instantly identify low-lying pixels vulnerable to SLR.
    2. Reclassifies output to create a clean binary raster of inundation zones.
    3. Saves time and ensures reproducibility across multiple areas and SLR scenarios.
    How does it works: Raster calculator identifies pixels below the reference sea level height, and reclassification isolates only the vulnerable pixels as a binary output raster.
    """""

    # todo: Raster Calculation for differentiating vulnerable pixels
    slh_raster = RasterCalculator(
        [input_dem], ["input"],
        expression=f'input <= {ht}'
    )
    slh_raster.save(rf"{InundatedRaster}\InunRas_{int(ht)}_{ref}_{scenario}.tif")
    arcpy.AddMessage(f"Calculating the Pixel was done and saved in Folder: {InundatedRaster}")

    # todo: Reclassifying to remove the safe pixels
    remap = "0 NODATA;1 1"
    out_raster = arcpy.sa.Reclassify(
        in_raster=rf"{InundatedRaster}\InunRas_{int(int(ht))}_{ref}_{scenario}.tif",
        reclass_field="Value",
        remap=remap,
        missing_values="DATA"
    )
    out_raster.save(rf"{InundatedRaster}\RemapInunRas_{int(ht)}_{ref}_{scenario}.tif")
    arcpy.AddMessage(f"Reclassifying the vulnerable Pixels was done and saved in Folder: {InundatedRaster}")

    # todo: Using Def function to produce final Polygons
    inun_area = raster_to_dissolved_area(
        in_raster_path    = rf"{InundatedRaster}\RemapInunRas_{int(ht)}_{ref}_{scenario}.tif",
        out_polygon_path  = rf"{InundatedPolygon}\InunPolygon_{int(ht)}_{ref}_{scenario}.shp",
        final_polygon_path= rf"{FinalInundatedPolygon}\Final_Inundation_{int(ht)}_{ref}_{scenario}.shp"
    )
    arcpy.AddMessage(f"Converting the vulnerable pixels to polygon was done and saved into  Folder: {InundatedPolygon}")
    arcpy.AddMessage("Completed with Area Calculation")

    """""
    1. Clips future land cover raster with inundation polygon to identify vulnerable LULC classes.
    2. Converts and dissolves output to generate polygons grouped by land cover type.
    3. Calculates area loss per LULC class, highlighting most susceptible land covers.
    How does it works: Clip tool extracts future land cover areas falling within the inundation polygon, and dissolve groups the output by land cover classes to calculate area loss per category.
    """""

    # todo: masking out the vulnerable LULC areas
    lulc_masked = arcpy.sa.ExtractByMask(
        in_raster=input_lulc,
        in_mask_data=rf"{FinalInundatedPolygon}\Final_Inundation_{int(ht)}_{ref}_{scenario}.shp"
    )
    lulc_masked.save(rf"{InundatedRaster}\LULC_InunRas_{int(ht)}_{ref}_{scenario}.tif")
    arcpy.AddMessage(f"Converting the vulnerable pixels to polygon was done and saved into  Folder: {InundatedPolygon}")

    # todo: Using Def function to produce final Polygons (LULC-based)
    lulc_area = raster_to_dissolved_area(
        in_raster_path    = rf"{InundatedRaster}\LULC_InunRas_{int(ht)}_{ref}_{scenario}.tif",
        out_polygon_path  = rf"{InundatedPolygon}\LULC_Polygon_{int(ht)}_{ref}_{scenario}.shp",
        final_polygon_path= rf"{FinalInundatedPolygon}\Final_LULC_Inundation_{int(ht)}_{ref}_{scenario}.shp"
    )
    arcpy.AddMessage("LULC Area Calculation Completed")

    # todo: Finding out the Area loss by each landcover for each of the scenarios
    fc_lulc = rf"{FinalInundatedPolygon}\Final_LULC_Inundation_{int(ht)}_{ref}_{scenario}.shp"
    arcpy.management.AddField(in_table=fc_lulc, field_name="LULC_Name", field_type="TEXT", field_length=50)
    with arcpy.da.UpdateCursor(fc_lulc, ["gridcode", "LULC_Name", "Area"]) as cursor:
        for row in cursor:
            row[1] = lulc_names.get(row[0], "Unknown")
            cursor.updateRow(row)

            results.append({
                "Year": ref,
                "Scenario": scenario,
                "Height": ht,
                "LULC": row[1],
                "Area_sqkm": row[2]
            })
    arcpy.AddMessage(f"Analysis completed for the Year: {ref} where SLH is expected to be {ht} for SSP Scenario {scenario}")

df_long = pd.DataFrame(results)
output_csv = arcpy.GetParameterAsText(9)

#todo: Producing figures based on LULC

df_final = df_long.pivot_table(
    index  = "Year", columns= "LULC", values = "Area_sqkm", aggfunc= "sum"
).reset_index()

df_final.columns.name = None  # clean up column axis name
arcpy.AddMessage(df_final)
df_final.to_csv(output_csv, index=False)
arcpy.AddMessage(f"CSV saved to: {output_csv}")
arcpy.AddMessage(f"Entire Analysis was completed successfully for the scenario {scenario} 😊")
