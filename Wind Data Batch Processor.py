# -*- coding: utf-8 -*-
"""
Wind Data Batch Processor
v. 1.0
18.3.2021
Wesa Perttola


This macro batch processes .netcdf wind u- and v-components into wind speed
and direction rasters. It utilizes ArcGIS Pro 2.5 tools and requires a Spatial
Analyst licence to run. See upcoming article

    Perttola, W. 2021: Digital Navigator on the Seas of the Selden Map
    of China: Sequential Least-Cost Path Analysis Using Dynamic Wind Data
    in the Early 17th Century South China Sea.  

for further details. The NetCDF files used in the study with the directory
structure needed for the macro are available for download at Zenodo
(c. 40 GB .7z file):

https://doi.org/10.5281/zenodo.4625061
"""


#------------------- IMPORT LIBRARIES -------------------
import arcpy, os, arrow


#------------------- CHECKOUT LICENCES -------------------
arcpy.CheckOutExtension("Spatial")


#-------------------SET ENVIRONMENT -------------------
# set start time
arw = arrow.Arrow(1979, 1, 1, 0)
# number of days to process
days_to_process = 31 * 4
# set file output location
arcpy.env.scratchWorkspace = r"C:/DN/temp/"
arcpy.env.workspace = r"C:/DN/"
os.chdir(r"C:/DN/")
# allow overwriting
arcpy.env.overwriteOutput = True


#------------------- INPUT DATA -------------------
# netcdf file names without .nc extension
wind_u_filename =  "wind_u"
wind_v_filename = "wind_v"
# land/sea (1/0) raster used for resample snapping and setting null
landraster_filename = "storage/land_sea.tif"


#------------------- DEFINE FUNCTIONS -------------------
def netcdf_to_dir_and_speed(nds_filenames, nds_datatype, nds_time):
    for loop_filename in nds_filenames:
        loop_filename_ext = loop_filename + ".nc"
        print(loop_filename + ": Making NETCDF points")
 
        # create points from netcdf
        nds_lon = arcpy.NetCDFFileProperties(r"netcdf/" + loop_filename_ext).getVariables()[1]
        nds_lat = arcpy.NetCDFFileProperties(r"netcdf/" + loop_filename_ext).getVariables()[0]
        nds_variable = arcpy.NetCDFFileProperties(r"netcdf/" + loop_filename_ext).getVariables()[3]
        row_dimensions = nds_lon + ";" + nds_lat
        arcpy.md.MakeNetCDFFeatureLayer(r"netcdf/" + loop_filename_ext, nds_variable, nds_lon, nds_lat, r"memory/" + loop_filename, row_dimensions, '', '', nds_time, "BY_VALUE")     

        # reproject from WGS84 to Asia South Equidistant Conic (ESRI:102029)
        print(loop_filename + ": Reprojecting")
        arcpy.management.Project(r"memory/" + loop_filename, r"temp/proj_" + loop_filename + ".shp", "PROJCS['Asia_South_Equidistant_Conic',GEOGCS['GCS_WGS_1984',DATUM['D_WGS_1984',SPHEROID['WGS_1984',6378137.0,298.257223563]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Equidistant_Conic'],PARAMETER['False_Easting',0.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',125.0],PARAMETER['Standard_Parallel_1',7.0],PARAMETER['Standard_Parallel_2',-32.0],PARAMETER['Latitude_Of_Origin',-15.0],UNIT['Meter',1.0]]",
                                 None, None, "NO_PRESERVE_SHAPE", None, "NO_VERTICAL")

        # interpolate
        print(loop_filename + ": Interpolating")
        arcpy.ddd.NaturalNeighbor(r"temp/proj_" + loop_filename + ".shp", nds_variable, r"memory/nat_" + loop_filename, landraster_filename)
        
        # clip
        print(loop_filename + ": Clipping")
        arcpy.management.Clip(r"memory/nat_" + loop_filename, "-2892045,90595181 1129654,52986545 -202045,905951815 4590154,52986545", r"memory/clip_" + loop_filename, landraster_filename, "-3,402823e+38",
                              "NONE", "NO_MAINTAIN_EXTENT")

    # calculate direction
    print(nds_datatype + ": Calculating direction")
    direction_temp = arcpy.sa.RasterCalculator([r"memory/clip_wind_u", r"memory/clip_wind_v"], ["u", "v"],
                                                  "(180 / 3.14159265358979323846) * ATan2(u, v)")
    direction_raster = arcpy.sa.Con(direction_temp < 0, direction_temp + 360, direction_temp) 
    direction_nullraster = arcpy.ia.SetNull(landraster_filename, direction_raster, "Value = 1")        
    direction_nullraster.save(r"wind/direction/wd" + savename_time + r".tif")
 
    # calculate speed
    print(nds_datatype + ": Calculating speed")
    speed_raster = arcpy.sa.RasterCalculator([r"memory/clip_wind_u", r"memory/clip_wind_v"], ["u", "v"],
                                              "sqrt(u * u  + v * v)")
    speed_nullraster = arcpy.ia.SetNull(landraster_filename, speed_raster, "Value = 1")
    speed_nullraster.save(r"wind/speed/ws" + savename_time + r".tif")


#------------------- MAIN PROGRAM -------------------
for i in range(1,days_to_process + 1):
    time = "TIME '" + arw.format('DD/MM/YYYY HH:mm:ss')+"'"
    print(str(i) + " ------------ " + time + " ------------ " + str(i))
    savename_time = arw.format('YYMMDDHH')
    
    # call function
    filenames = [wind_u_filename, wind_v_filename]
    datatype = "wind"
    netcdf_to_dir_and_speed(filenames, datatype, time)
    
    # advance time
    arw = arw.shift(hours=+6)
    

#------------------- END -------------------
print("DONE!")   
    
