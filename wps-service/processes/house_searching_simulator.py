import os
import sys
# PostGIS sets GDAL_DATA and PROJ_LIB on the system environments to its own folders, and due to that fiona stopped working properly.
# The next two lines will remove those variables from the environment dictionary. 
os.environ.pop('GDAL_DATA', None)
os.environ.pop('PROJ_LIB', None)

from enum import IntEnum

from pywps import Process, LiteralInput, LiteralOutput
from osgeo import gdal
from osgeo import ogr
from geo.Geoserver import Geoserver

import subprocess
import json

# The inputs should be simple inputs, as the inputs are from a form.
# The first is school minimum distances, and near or far

class FunctionType(IntEnum):
    NEAR = 1
    FAR = 2
    MIDPOINT = 3

# My class needs to inherit from the Process class
class HouseSearchSimulator(Process):
    BASE_PATH = os.getcwd()
    DATA_PATH = os.path.join(BASE_PATH, "data")
    OUTPUT_PATH = os.path.join(BASE_PATH, "outputs")
    GDAL_CALC_PATH = os.path.join(os.getcwd(), '.venv/Scripts/gdal_calc.py')

    def __init__(self):
        # Need inputs for:
        # ComplexInput in Json { ' 'CriteriaType': 1, 'FunctionType': 1, 'Weight': 1 } 
        inputs = [LiteralInput('data', 'data', data_type="string")]
        outputs = [LiteralOutput('response', 'Output response', data_type='boolean')]

        # Set the attributes
        super(HouseSearchSimulator, self).__init__(
            self._handler,
            identifier='simulator',
            title='Process House Searching Simulator',
            abstract='Returns a literal string output\
             with Hello plus the inputed name',
            version='1.3.3.7',
            inputs=inputs,
            outputs=outputs,
            store_supported=True,
            status_supported=True
        )

    def _handler(self, request, response):
        # Here we do the actual geospatial analysis
        # First step is to define what is necessary
        # Second step is to derive from the define, meaning, to make sure that any vector data is rasterized and raster data is correct.
        # 1 - Start with the school distance analysis
        #     Schools locations are on the database, so we need to retrieve it first with ogr or gdal
        #     Once locations are retrieved, rasterize them. (Derive)

        # Parse inputs from request
        data = json.loads(request.inputs['data'][0].data)
        criteria = data["Criteria"]
        # Derive
        self.derive()
        # Transform
        school_reclass, metro_reclass = self.transform(criteria)
        # Weight and Combine
        suitability = self.weight_combine((school_reclass, criteria[0]["Weight"]), (metro_reclass, criteria[1]["Weight"]))
        # Locate suitable regions
        suitableregions = self.locate(suitability)

        # Send the suitability map to geoserver
        self.submit_to_geoserver(suitableregions)

        #TODO: In case of failure in any of the steps before, return False, use a try catch finally.

        response.outputs['response'].data = True

        return response
    
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
    
    def _calculate_function(self, function_type, values):
        if function_type == FunctionType.FAR:
            return f"10*(A>{values[0]}) + 5*(A>{values[1]})*(A<={values[0]}) + 1*(A<{values[1]})"
        if function_type == FunctionType.MIDPOINT:
            return f"1*(A<{values[0]}) + 1*(A>{values[1]}) + 5*(A>{values[2]})*(A<={values[1]}) + 10*(A>={values[0]})*(A<={values[2]})"

    def derive(self):
        # Derive school distance
        schools_shapefile_location = os.path.join(self.DATA_PATH, "POIEducacao")
        schools_raster_filename = os.path.join(self.OUTPUT_PATH, "schools.tif")
        schools_proxmity_raster_filename = os.path.join(self.OUTPUT_PATH, "distance_schools.tif")
        self._generate_raster(schools_shapefile_location, schools_raster_filename)
        self._compute_proximity(schools_raster_filename, schools_proxmity_raster_filename)

        # Derive metro distance
        metro_shapefile_location = os.path.join(self.DATA_PATH, "POITransportes")
        metro_raster_filename = os.path.join(self.OUTPUT_PATH, "metro.tif")
        metro_proxmity_raster_filename = os.path.join(self.OUTPUT_PATH, "distance_metro.tif")
        self._generate_raster(metro_shapefile_location, metro_raster_filename)
        self._compute_proximity(metro_raster_filename, metro_proxmity_raster_filename)
        return
    
    def transform(self, criteria):
        #TODO: The calculation variables need to come from the WPS inputs
        distance_school_file = os.path.join(self.OUTPUT_PATH, "distance_schools.tif")
        distance_school_file_reclass = os.path.join(self.OUTPUT_PATH, "distance_schools_reclass.tif")
        calc = self._calculate_function(criteria[0]["FunctionType"], (20, 15)) #TODO: Not good enough, need to improve, but not important at this stage ...
        subprocess.call([sys.executable, self.GDAL_CALC_PATH, '-A', distance_school_file, '--outfile', distance_school_file_reclass , f'--calc="{calc}"' ])

    	#TODO: The calculation variables need to come from the WPS inputs
        metro_school_file = os.path.join(self.OUTPUT_PATH, "distance_metro.tif")
        metro_school_file_reclass = os.path.join(self.OUTPUT_PATH, "distance_metro_reclass.tif")
        calc = self._calculate_function(criteria[1]["FunctionType"], (10, 40, 20)) #TODO: Not good enough, need to improve, but not important at this stage ...
        subprocess.call([sys.executable, self.GDAL_CALC_PATH, '-A', metro_school_file, '--outfile', metro_school_file_reclass , f'--calc="{calc}"' ])

        return distance_school_file_reclass, metro_school_file_reclass
    
    def weight_combine(self, *args):
        #TODO: The weights need to come from the WPS inputs
        startChar = 'A'
        currChar = startChar
        values = ()
        calc = ""
        suitability_filename = os.path.join(self.OUTPUT_PATH, "suitability.tif")

        for arg in args:
            values = values + ("-"+currChar, arg[0])
            if calc:
                calc = calc + " + "
            calc = calc + str(arg[1]) + "*" + currChar
            currChar = chr(ord(currChar) + 1)
        values += ('--outfile', suitability_filename)
        values += ('--extent', "intersect")
        values += ('--overwrite', )
        finalCalc = f"({calc})/{len(args)}"
        
        subprocess.call([sys.executable, self.GDAL_CALC_PATH, *values , f'--calc="{finalCalc}"' ])
        return suitability_filename
    
    def locate(self, suitabilitymap):
        nodatavalue = '0'
        suitableregions = os.path.join(self.OUTPUT_PATH, "final_suitability_map.tif")
        calc = "0*(A<13)+1*(A>=13)"
        subprocess.call([sys.executable, self.GDAL_CALC_PATH, '-A', suitabilitymap, '--outfile', suitableregions, f'--calc="{calc}"', '--NoDataValue', nodatavalue, '--overwrite' ])
        return suitableregions

    def submit_to_geoserver(self, suitableregions, email):
        geo = Geoserver('http://127.0.0.1:8080/geoserver', username='admin', password='geoserver')
        workspace = 'csig'
        # This will take care of everything in one line instead of having to do manually the following tasks
        # 1 - Create geotiff store on the defined workspace
        # 2 - Add new layer to the store created in #1
        # 3 - Publish layer created in #2 
        geo.create_coveragestore(layer_name=f'SuitabilityRegions_{email}', path=suitableregions, workspace=workspace)