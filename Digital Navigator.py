# -*- coding: utf-8 -*-
"""
Digital Navigator
v. 1.0
18.3.2021
Wesa Perttola


This macro simulates ancient sail-powered voyages using sequential least-cost
path analysis based on deterministic time series wind data. It utilizes ArcGIS
Pro 2.5 tools and requires a Spatial Analyst licence to run. See upcoming
article

    Perttola, W. 2021: Digital Navigator on the Seas of the Selden Map
    of China: Sequential Least-Cost Path Analysis Using Dynamic Wind Data
    in the Early 17th Century South China Sea.  

for further details. A four month (1.1.-30.4.1979) 6-hourly test dataset
with the directory structure needed for the macro is available for download 
at Zenodo (c. 40 GB .7z file):

https://doi.org/10.5281/zenodo.4625061
"""


#------------------- IMPORT LIBRARIES -------------------
import arcpy, os, arrow

#-------------------  CHECKOUT LICENCES -------------------
arcpy.CheckOutExtension("Spatial")

#-------------------  SET ENVIRONMENT -------------------
# set file output location
arcpy.env.scratchWorkspace = r"C:/DN/temp/"
arcpy.env.workspace = r"C:/DN/"
os.chdir(r"C:/DN/")
# allow overwriting
arcpy.env.overwriteOutput = True


#-------------------  INPUT DATA -------------------
# set start time
arw = arrow.Arrow(1979, 1, 1, 0)
# number of days to process
days_to_process = 31
# path start point
start_point = r"storage/start_point.shp"
# path end point
end_point = r"storage/end_point.shp"
# horizontal factor table
horizontal_factor = r"C:/DN/storage/horizontal_factor_table.txt"
# extra cost rasters
shallows_cost = arcpy.sa.Raster(r"storage/shallows_cost.tif")
islands_cost = arcpy.sa.Raster(r"storage/islands_cost.tif")


#------------------- SHIP SETTINGS -------------------
# ship speed to wind speed ratio
shipv_to_windv = 0.4
# top speed treshold (m/s)
top_speed_treshold = 25 * 0.51444444444 * shipv_to_windv # @ 25 knots wind, mid Beaufort Force 6
# storm treshold at wind speed (m/s)
storm_treshold = 40 * 0.51444444444 * shipv_to_windv # @ 40 knots wind, high Beaufort Force 8 
# speed in storms (>lower_treshold) (m/s)
storm_speed = 0.5 * 0.51444444444 # = 0.5 knots  


#------------------- MAIN PROGRAM -------------------
# start point to raster
with arcpy.EnvManager(snapRaster=r"storage/land_sea.tif"):
    arcpy.conversion.PointToRaster(start_point, "FID", r"memory/start_point_ras", "MOST_FREQUENT", "NONE", r"storage/land_sea.tif")
start_point_temp = arcpy.sa.Raster(r"memory/start_point_ras")
start_point_ras = arcpy.sa.Con(arcpy.sa.IsNull(start_point_temp), 0, 1)
start_point_ras.save(r"memory/start_point_ras.tif")

# end point to raster
with arcpy.EnvManager(snapRaster=r"storage/land_sea.tif"):
    arcpy.conversion.PointToRaster(end_point, "FID", r"memory/end_point_ras", "MOST_FREQUENT", "NONE", r"storage/land_sea.tif")
end_point_temp = arcpy.sa.Raster(r"memory/end_point_ras")
end_point_ras = arcpy.sa.Con(arcpy.sa.IsNull(end_point_temp), 0, 1)
end_point_ras.save(r"memory/end_point_ras.tif")

# get end point coordinates for the first row in the table
with arcpy.da.SearchCursor(end_point, ["SHAPE@X"]) as cursor:
    row = next(cursor)
    end_xcoord = row[0]
with arcpy.da.SearchCursor(end_point, ["SHAPE@Y"]) as cursor:
    row = next(cursor)
    end_ycoord = row[0]
coordinates = str(end_xcoord) + " " + str(end_ycoord)

# daily loop
for i in range(1, days_to_process + 1):  
     
    # set start values
    loop_start_point = arcpy.sa.Raster(r"memory/start_point_ras.tif")
    horizontal_factor_text = r"TABLE " + horizontal_factor
    arcpy.CopyRaster_management("memory/start_point_ras.tif", r"memory/path_mosaic", "", "", "", "NONE", "NONE", "")
    time_accumulation = 0
    loop_counter = 0
    highest_wind = 0
    lowest_wind = 1000
    end_point_value_str = "NoData"
    arw_counter = arw    
    filename_day = arw.format('YYMMDDHH')
    
 
    print("============================= Start of day " + arw.format('DD/MM/YYYY') + " =============================")
    
    # 6-hour loop
    while end_point_value_str == "NoData":
        # format time        
        time = "TIME '" + arw_counter.format('DD/MM/YYYY HH:mm:ss')+"'"
        print("------------ " + time + "------------")
        filename_time = arw_counter.format('YYMMDDHH')

        # advance loop counter
        loop_counter = loop_counter + 1
        print("Loop counter: " + str(loop_counter))
        
        # rescale wind speed to ship speed  
        print("Rescaling wind")
        wind_speed = arcpy.sa.Raster(r"wind/speed/ws" + filename_time + r".tif")
        wind_speed_ratioed = wind_speed * shipv_to_windv
        # wind_speed_ratioed.save(r"temp/ra" + filename_time + r".tif") # debug save
        # calculate line slope: y=kx+b -> k=(y2-y1)/(x2-x1)
        k = (storm_speed - top_speed_treshold) / (storm_treshold - top_speed_treshold) 
        # calculate line intercept: y=kx+b -> b=y1-kx1
        b = top_speed_treshold - k * top_speed_treshold
        # lower the speed if speed > top_speed_treshold
        speed_rescale = arcpy.sa.Con(wind_speed_ratioed <= top_speed_treshold, wind_speed_ratioed,
                                      arcpy.sa.Con((wind_speed_ratioed > top_speed_treshold) & (wind_speed_ratioed <= storm_treshold), k * wind_speed_ratioed + b,
                                                  arcpy.sa.Con(wind_speed_ratioed > storm_treshold, storm_speed)))
        # speed_rescale.save(r"temp/sr" + filename_time + r".tif") # debug save
        
        # calculate cost (seconds/meter)
        print("Calculating cost")
        cost_per_m = 1 / speed_rescale * shallows_cost * islands_cost 
        # cost_per_m.save(r"temp/cost.tif") # debug save
        
        # calculate path distance
        print("Pathing distance")
        path_dist = arcpy.sa.PathDistance(loop_start_point, cost_per_m, None, r"wind/direction/wd" + filename_time + r".tif", horizontal_factor_text,
                                          None, None, None, r"memory/backlink", None, None, None, None, '')
        # path_dist.save(r"temp/pathdist.tif") # debug save
        # arcpy.CopyRaster_management(r"memory/backlink", r"/temp/backlink.tif", "", "", "", "NONE", "NONE", "") # debug save
        
        # # calculate least cost path
        print("Least cost pathing") 
        least_cost_path = arcpy.sa.CostPath(r"memory/end_point_ras.tif", path_dist, r"memory/backlink", "EACH_CELL", "Value", "INPUT_RANGE"); 
        # least_cost_path.save(r"temp/LCP.tif") # debug save 
        
        # overlay path distance to least cost path
        print("Overlaying path distance")
        path_overlay = arcpy.sa.Con((least_cost_path) & (path_dist <= 21600), path_dist) # 21600 s = 6 h
        path_overlay.save(r"memory/path_overlay")
        # path_overlay.save(r"temp/path_overlay.tif") # debug save 
        
        # find maximum value from path overlay
        max_path_value = path_overlay.maximum
        time_accumulation = time_accumulation + max_path_value
        print("Time accumulated so far: " + str(round(time_accumulation/86400, 2)) + " days") # 86400 s = 24 h
        loop_start_point = arcpy.sa.Con(path_overlay == max_path_value, 1)
        # loop_start_point.save(r"temp/new_start_position.tif") # debug save 
        
        # overlay wind speed to path
        print("Overlaying wind speed")
        wind_overlay = arcpy.sa.Con(path_overlay >=0, wind_speed)
        # wind_overlay.save(r"temp/wind_overlay.tif") # debug save 
       
        # find maximum and minimum wind on path
        max_wind_value = wind_overlay.maximum
        if max_wind_value > highest_wind:
            highest_wind = max_wind_value
        print("Highest wind on segment: " + str(round(max_wind_value, 2)) + " m/s")
        print("Highest wind so far: " + str(round(highest_wind, 2)) + " m/s")

        min_wind_value = wind_overlay.minimum
        if min_wind_value < lowest_wind:
            lowest_wind = min_wind_value
        print("Lowest wind on segment: " + str(round(min_wind_value, 2)) + " m/s")
        print("Lowest wind so far: " + str(round(lowest_wind, 2)) + " m/s")
        
        # combine path segments
        print("Combining path segments")
        arcpy.management.MosaicToNewRaster("memory/path_mosaic;memory/path_overlay", r"/temp", "temp_merge.tif", None, "32_BIT_FLOAT", None, 1, "LAST", "FIRST")
        arcpy.CopyRaster_management(r"/temp/temp_merge.tif", r"memory/path_mosaic", "", "", "", "NONE", "NONE", "")
        
        # advance time    
        arw_counter = arw_counter.shift(hours=+6)   
        
        # get segment end point coordinates
        result = arcpy.GetCellValue_management(r"memory/path_mosaic", coordinates, "1")
        end_point_value_str = str(result.getOutput(0))
    
    # save results: route raster + txt (start date; accumulated time; number of loops; highest wind, lowest wind)
    print("SAVING THE DAY")
    file_object = open("storage/results.txt", "a")
    file_object.write(filename_day + ";" + str(time_accumulation/86400) + ";" + str(loop_counter) + ";"  + str(highest_wind) + ";" + str(lowest_wind) + "\n")
    file_object.close()

    mosaic_temp = arcpy.sa.Raster(r"memory/path_mosaic") 
    mosaic_result = arcpy.sa.Con(mosaic_temp >= 0, 1)      
    arcpy.CopyRaster_management(mosaic_result, r"/routes/r" + filename_day + r".tif", "", "", "", "NONE", "NONE", "")

    # advance time    
    arw = arw.shift(days=+1)   

#------------------- END -------------------
print("DONE!")   

