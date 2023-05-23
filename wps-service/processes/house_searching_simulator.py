import os
import sys
import shutil
import subprocess
import json

# PostGIS sets GDAL_DATA and PROJ_LIB on the system environments to its own folders
# The next two lines will remove those variables from the environment dictionary to prevent issues.
os.environ.pop('GDAL_DATA', None)
os.environ.pop('PROJ_LIB', None)

from enum import IntEnum

# Allows the implementation of a process of a wps service.
from pywps import Process, ComplexInput, ComplexOutput, Format, FORMATS

# The core of the implemention of a suitability modelling (or a multi-criteria analysis) 
from osgeo import gdal
from osgeo import ogr

# Required for this process to be able to send the result of the analysis to geoserver.
from geo.Geoserver import Geoserver

# This an enum that allows mapping a number (it will come from the frontend as numbers) to a specific type
# This allows to understand what criteria the user wants to define what's a good distance type from something.
# For instance if the person wants to be close to something, or far from it, or somewhere where it's not far or near.
class FunctionType(IntEnum):
    NEAR = 1
    FAR = 2
    MIDPOINT = 3

class HouseSearchSimulator(Process):
    base_path = os.getcwd()
    data_path = os.path.join(base_path, "../data")
    output_path = os.path.join(base_path, "outputs")
    gdal_calc_path = os.path.join(base_path, '.venv/Scripts/gdal_calc.py')
    user_specific_output_path = output_path # will be set later after the process starts.

    def __init__(self):
        inputs = [ComplexInput('data', 'data', supported_formats=[Format('application/json')])]
        outputs = [ComplexOutput('response', 'Output response', supported_formats=[Format('application/json')])]

        # Set the attributes
        super(HouseSearchSimulator, self).__init__(
            self._handler,
            identifier='simulator',
            title='Process House Searching Simulator',
            abstract='This process does a multi-criteria analysis to recommend specific locations, depending on the user input',
            inputs=inputs,
            outputs=outputs
        )

    def _handler(self, request, response):
        # Here we do the actual geospatial analysis based on:
        # - Idea: https://desktop.arcgis.com/en/analytics/case-studies/understanding-the-suitability-modeling-workflow.htm
        # - Example with GDAL: https://spatialthoughts.com/2022/01/31/multi-criteria-overlay-gdal/

        # Parse inputs from request
        data = json.loads(request.inputs['data'][0].data)
        criteria = data["Criteria"]
        person_id = data["PersonId"]
        
        # Create user specific folder which will be deleted in the end. This will be basically where temporary raster files are used
        # to create the final suitable locations raster, which will be uploaded to Geoserver.
        self.user_specific_output_path = os.path.join(self.output_path, person_id)
        self._create_folder(self.user_specific_output_path)

        # Derive
        proximity_files = self._derive() # It returns an array of file paths in the order of School, Metro and Roads, the rest of the code knows about this order.
        # Transform
        transformations = self._transform(criteria, proximity_files)
        # Weight and Combine
        suitability = self.weight_combine(transformations, criteria)
        # Locate suitable regions
        suitableregions = self.locate(suitability, person_id)
        # Send the suitability map to geoserver
        url, layer = self.submit_to_geoserver(suitableregions, person_id)

        out_bytes = json.dumps(json.loads('{"url":"'+ url +'","layer":"' + layer + '"}'))

        response.outputs['response'].data_format = FORMATS.JSON
        response.outputs['response'].data = out_bytes

        # Cleanup raster files that are no longer needed.
        self._delete_folder(self.user_specific_output_path)

        return response

    # Required to create a user specific folder.
    def _create_folder(self, path):
        if os.path.exists(path):
            return

        # function makedirs allows to create folders and subfolders, unlike mkdir
        os.makedirs(path)

    def _delete_folder(self, path):
        if os.path.exists(path):
            shutil.rmtree(path)
    
    def _generate_raster(self, infile, outfile):
        # inspired by http://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html#convert-an-ogr-file-to-a-raster
        pixel_size = 25
        nodata_value = -9999

        source_ds = ogr.Open(infile)
        source_layer = source_ds.GetLayer()
        x_min, x_max, y_min, y_max = source_layer.GetExtent()

        # Generate tif file now
        x_res = int((x_max - x_min) / pixel_size)
        y_res = int((y_max - y_min) / pixel_size)
        target_ds = gdal.GetDriverByName("GTiff").Create(outfile, x_res, y_res, 1, gdal.GDT_Byte)
        target_ds.SetGeoTransform((x_min, pixel_size, 0, y_max, 0, -pixel_size))
        target_ds.SetProjection(source_layer.GetSpatialRef().ExportToWkt())
        band = target_ds.GetRasterBand(1)
        band.SetNoDataValue(nodata_value)

        # Rasterize
        gdal.RasterizeLayer(target_ds, [1], source_layer, burn_values=[1])
        
        # delete input and output rasters
        del source_ds, target_ds

    def _compute_proximity(self, infile, outfile):
        # inspired by https://github.com/marcelovilla/gdal-py-snippets/blob/master/scripts/compute_proximity.py

        # open rasterized file and get information
        ds = gdal.Open(infile, 0)
        band = ds.GetRasterBand(1)
        gt = ds.GetGeoTransform()
        sr = ds.GetProjection()
        cols = ds.RasterXSize
        rows = ds.RasterYSize

        # create empty proximity raster
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(outfile, cols, rows, 1, gdal.GDT_Byte)
        out_ds.SetGeoTransform(gt)
        out_ds.SetProjection(sr)
        out_band = out_ds.GetRasterBand(1)

        # compute proximity
        gdal.ComputeProximity(band, out_band, ['VALUES=1', 'DISTUNITS=PIXEL'])

        # delete input and output rasters
        del ds, out_ds
        
    def _derive(self):
        # TODO: These files are always the same, we could verify first if the files already exist to prevent unnecessary processing, but I'll accept the Tech Debt
        def _inner_derive(shapefile_name, raster_name, proximity_name):
            shapefile_file = os.path.join(self.data_path, shapefile_name)
            raster_file = os.path.join(self.output_path, raster_name)
            proximity_file = os.path.join(self.output_path, proximity_name)
            self._generate_raster(shapefile_file, raster_file)
            self._compute_proximity(raster_file, proximity_file)
            return proximity_file

        # Derive school distance
        school_proximity_file = _inner_derive("POIEducacao", "schools.tif", "distance_schools.tif")

        # Derive metro distance
        metro_proximity_file = _inner_derive("POITransportes", "metro.tif", "distance_metro.tif")

        # Derive roads distance
        roads_proximity_file = _inner_derive("RedeViaria", "roads.tif", "distance_roads.tif")

        return [school_proximity_file, metro_proximity_file, roads_proximity_file]
    
    def _calculate_function(self, function_type, values):
        # TODO: This implementation is admittedly not good, would need to completely rethink. This is a project by itself.
        if function_type == FunctionType.NEAR:
            return f"10*(A<={values[0]}) + 5*(A>{values[0]})*(A<={values[1]}) + 1*(A>{values[1]})"
        if function_type == FunctionType.FAR:
            return f"10*(A>={values[1]}) + 5*(A>{values[0]})*(A<{values[1]}) + 1*(A<={values[0]})"
        if function_type == FunctionType.MIDPOINT:
            return f"1*(A<{values[0]}) + 1*(A>{values[2]}) + 5*(A<{values[1] - 5})*(A>{values[1] + 5}) + 10*(A>={values[1] - 5})*(A<={values[1] + 5})"
    
    def _transform(self, criteria, proximity_files):
        distance_school_file_reclass = os.path.join(self.user_specific_output_path, "distance_schools_reclass.tif")
        calc = self._calculate_function(criteria[0]["FunctionType"], (10, 30, 50)) #TODO: The values should be decided by the user, not by code
        subprocess.call([sys.executable, self.gdal_calc_path, '-A', proximity_files[0], '--outfile', distance_school_file_reclass , f'--calc="{calc}"' ])

        metro_school_file_reclass = os.path.join(self.user_specific_output_path, "distance_metro_reclass.tif")
        calc = self._calculate_function(criteria[1]["FunctionType"], (10, 30, 50)) #TODO: The values should be decided by the user, not by code
        subprocess.call([sys.executable, self.gdal_calc_path, '-A', proximity_files[1], '--outfile', metro_school_file_reclass , f'--calc="{calc}"' ])

        roads_school_file_reclass = os.path.join(self.user_specific_output_path, "distance_roads_reclass.tif")
        calc = self._calculate_function(criteria[2]["FunctionType"], (5, 13, 20)) #TODO: The values should be decided by the user, not by code
        subprocess.call([sys.executable, self.gdal_calc_path, '-A', proximity_files[2], '--outfile', roads_school_file_reclass , f'--calc="{calc}"' ])

        return [distance_school_file_reclass, metro_school_file_reclass, roads_school_file_reclass]
    
    def weight_combine(self, transformations, criteria):
        startChar = 'A'
        currChar = startChar
        values = ()
        calc = ""
        suitability_filename = os.path.join(self.user_specific_output_path, "suitability.tif")
        weightSum = 0

        for x in range(3):
            values = values + ("-"+currChar, transformations[x])
            if calc:
                calc = calc + " + "
            calc = calc + str(criteria[x]['Weight']) + "*" + currChar
            currChar = chr(ord(currChar) + 1)
            weightSum += criteria[x]['Weight']
        values += ('--outfile', suitability_filename)
        values += ('--extent', "intersect")
        values += ('--overwrite', )
        finalCalc = f"({calc})/{weightSum}"
        
        subprocess.call([sys.executable, self.gdal_calc_path, *values , f'--calc="{finalCalc}"' ])

        # Clip the raster
        boundary_file = os.path.join(self.data_path, "StudyArea")
        suitability_clipped_filename = os.path.join(self.user_specific_output_path, "suitability_clipped.tif")
        ds = gdal.Open(suitability_filename)
        gdal.Warp(suitability_clipped_filename, ds, cutlineDSName = boundary_file, cropToCutline= True, dstNodata = "-999")
        del ds
        return suitability_clipped_filename
    
    def locate(self, suitabilitymap, person_id):
        nodatavalue = '0'
        suitableregions = os.path.join(self.user_specific_output_path, f"final_suitability_map_{person_id}.tif")
        calc = "0*(A<8)+A*(A>=8)"
        subprocess.call([sys.executable, self.gdal_calc_path, '-A', suitabilitymap, '--outfile', suitableregions, f'--calc="{calc}"', '--NoDataValue', nodatavalue, '--overwrite' ])
        return suitableregions

    def submit_to_geoserver(self, suitable_regions, person_id):
        geo = Geoserver('http://127.0.0.1:8080/geoserver', username='admin', password='geoserver')
        workspace = 'csig'
        layer_name = f'SuitabilityRegions_{person_id}'
        style_name = 'suitability_style'
        # This will take care of everything in one line instead of having to do manually the following tasks
        # 1 - Create geotiff store on the defined workspace
        # 2 - Add new layer to the store created in #1
        # 3 - Publish layer created in #2 
        geo.create_coveragestore(layer_name=layer_name, path=suitable_regions, workspace=workspace)
        # 4 - Update layer with the properly styling. This script assumes it is there already. If it's not,
        # an admin should go to geoserver and create it. It's not the responsibility of this process.
        geo.publish_style(layer_name=layer_name, style_name=style_name, workspace=workspace)
        return "http://localhost:8080/geoserver/wms", f"{workspace}:{layer_name}"