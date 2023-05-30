import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
import time
from datetime import datetime
from pyproj import CRS

# Objective of version 3 :
# speed it up (there are probably redundancies)
# investigate cartopy, seems like a better route for plotting actually
# if anything, this really probably should be a heatmap, and not a scatter plot.
# maybe it's not so stupid to be able to set a t_min and t_max. that way if animation is interrupted, we can start from later on?
# it's kind of annoying actually that the blue isn't all that impressive because if a latitude and longitude isn't "exactly right" well it won't be summed...

# a numpy approach of a mesh grid could be fine, so that points would be accumulated in areas
# and also computations arent too long. apparently scipy has good content for sparse matrices.
# MIGRATE TO GITHUB BECAUSE ACTUALLY MANUAL VERSIONING IS A MESS IF I WANT TO IMPLEMENT AN IDEA TO FUNCTIONAL OR TEST

# Set snapshot names - timesteps will be added automatically
snapshot_name = 'sodermalm'
print("Snapshots will be saved under the name:", snapshot_name)

# Step 1: Read the CSV file into a Pandas DataFrame, filtering out rows with N/A timesteps
# Note to self : explain Int64. int doesnt work, perhaps with 20000 etc, creats N/A
df = pd.read_csv('traffic_data.csv',
                    usecols=['timestep', 'longitude', 'latitude', 'CO2'],
                    dtype={'timestep': 'Int64', 'longitude': float, 'latitude': float, 'CO2': float}).dropna()

# KNOWING ORIGINAL CRS OF THE DATA? SPECIFY IT IN THE IMPROT
input_crs = CRS.from_epsg(4326)
print(f"Data obtained from CRS: {input_crs.name}")
#COMMENT WHAT THESE ARE EXACTLY

# Specify the CRS to be projected. Here, EPSG:3847 means pseudo-Mercator, but it can be changed.
#4814 is Stockholm
output_crs = CRS.from_epsg(4814)
print(f"Reprojecting to: {output_crs.name}")

# Step 2: Create a GeoDataFrame from the DataFrame
geometry = gpd.points_from_xy(df['longitude'], df['latitude'])
gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=input_crs)

# Reproject
gdf.to_crs(output_crs)

# Group data by latitude and longitude, and calculate the sum of CO2 values for each location
groupedCO2 = gdf.groupby(['latitude', 'longitude'])['CO2'].sum()

# Calculate the maximum CO2 pollution at a single point
max_CO2 = groupedCO2.max()


print(f"Longitudes x latitudes explored: {len(gdf['longitude'])} x  {len(gdf['latitude'])}")



# Step 3: Calculate the bounding box coordinates
min_lon, min_lat, max_lon, max_lat = gdf.total_bounds

# Adjust the CO2 unit and colorbar label based on the maximum value
# Determine the appropriate unit for the colorbar
if max_CO2 >= 1000:
    gdf['CO2'] /= 1000
    max_CO2 /= 1000
    unit = 'kilograms'
    if max_CO2 >= 1000:
        gdf['CO2'] /= 1000
        max_CO2 /= 1000
        unit = 'tons'
else:
    unit = 'grams'

# Step 5: Set up the figure and axes
fsize = 20
fig, ax = plt.subplots(figsize = (fsize, fsize))
# Explain exactly what fig and ax are ! The figure and the colorbar, subplots side to side. This is where we control the size.
ax.set_aspect('equal')
ax.set_axis_off()
ax.set_xlim(min_lon, max_lon)
ax.set_ylim(min_lat, max_lat)

# Calculate the appropriate zoom level based on the extent of the data
#zoom_level = ctx.tile._calculate_zoom(min_lat, max_lat, min_lon, max_lon)
#print(zoom_level) apparently 5 ?

# Adjust the zoom level to fit within the valid range
#zoom_level = min(zoom_level, 18)  # Set the maximum valid zoom level



print("Initializing colorbar...")
# Initialize the colorbar with the maximum CO2 value
colormap = 'plasma'
scatter_size = 1
sc = ax.scatter([], [], c=[], cmap=colormap, s=5, vmin=0, vmax=max_CO2)
cbar = plt.colorbar(sc, ax=ax, label=f'CO2 Pollution ({unit})', shrink=0.5)

# Uh oh, initialization is more complicated than expected!
'''To initialize "accumulated_values", we need all latitude and longitude where there was ever pollution. That way, we can create a fixed-length structure that will work throughout the whole simulation. So, we need to initialize a geodataframe using all longitudes and latitudes. It will store values of CO2 over time, and be initialized at zero. The goal is that, in the for loop, we can add pollution values at each timestep without any problems.'''
print("Initializing cumulative GeoDataFrame...")
# Get unique pairs of latitude and longitude
unique_locations = gdf[['latitude', 'longitude']].drop_duplicates()

# Create an empty GeoDataFrame with unique locations
CO2_df = pd.DataFrame(unique_locations, columns=['latitude', 'longitude'])
CO2_geometry = gpd.points_from_xy(CO2_df['longitude'], CO2_df['latitude'])
CO2_gdf = gpd.GeoDataFrame(CO2_df, geometry=CO2_geometry)

# Add a column 'CO2' filled with zeroes
CO2_gdf['CO2'] = 0

# Iterate over each timestep and update CO2 values
for timestep in gdf['timestep'].sort_values().unique():
    start_time = time.time()
    # Filter rows for the current timestep
    timestep_data = gdf[gdf['timestep'] == timestep]

    # Update CO2 values in the result DataFrame
    for index, row in timestep_data.iterrows():
        #Perhaps for loops are still too slow, and some native GeoPandas functions are better.
        location_match = (CO2_gdf['latitude'] == row['latitude']) & (CO2_gdf['longitude'] == row['longitude'])
        CO2_gdf.loc[location_match, 'CO2'] += row['CO2']
    CO2_values = CO2_gdf[timestep_data.index]

# Update the scatter plot
    sc = ax.scatter(
        CO2_geometry.x,
        CO2_geometry.y,
        c=CO2_values,
        cmap=colormap,
        s=scatter_size,
        vmin=0,
        vmax=max_CO2,
    )

    # Add the basemap with the calculated zoom level
    # ctx.add_basemap(ax, crs=gdf.crs, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5, zoom=zoom_level)
    ctx.add_basemap(ax, crs=gdf.crs, source=ctx.providers.OpenStreetMap.Mapnik)
    # additional unspecifies arguments : alpha=1, zoom=14
    #zoom provides a balance between low and high detail. Starting at 12 for reasonable info, 18 is max but takes huge amounts to generate.
    # To have an idea : 12 zoom takes a few seconds to generate, has abt 900 kb without further compression, is blurry.
    # 16 zoom takes
    # Explain this funky alpha value
    #cbar.ax.set_ylabel(f'CO2 Pollution ({unit})')

    end_time = time.time()  # Stop measuring the time
    # Calculate the elapsed time
    elapsed_time = end_time - start_time

    # Print the elapsed time in seconds
    print(f"-= Snapshot {timestep} =-")
    print(f"Generation time: {elapsed_time:.2f} seconds")

    # Get the size of the file in bytes
    file_size = os.path.getsize(filename)

    # Convert the file size to KB or MB
    if file_size < 1024:  # Less than 1 KB
        size_str = f"{file_size} bytes"
    elif file_size < 1024 ** 2:  # Less than 1 MB
        size_str = f"{file_size / 1024:.2f} KB"
    else:  # Larger than 1 MB
        size_str = f"{file_size / (1024 ** 2):.2f} MB"

    # Print the file size
    print(f"Dataframe size: {len(CO2_gdf)}")
    print(f"File size: {size_str}")

# Step 7: Display a message indicating the snapshots have been saved
print("Snapshots saved successfully.") 

# Add some prints yeah. But allow them to be turned off altogether. Perhaps seperate functions into stuff like the file size truncator.

