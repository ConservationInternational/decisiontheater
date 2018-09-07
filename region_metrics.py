# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)

def get_degradation_areas(geojson):
    """Return a list of areas within each degradation class for all polygons in geojson"""
    aoi = ee.Geometry(json.loads(geojson))
    "Returns area within each of the five degradation classes for each feature in a geojson"
    # load trends.earth land productivity indicator from assets (original 7 cl, remap to 5 cl)
    te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis").remap([-32768,1,2,3,4,5,6,7],[-32768,-2,-2,0,0,0,2,2])

    # define the names of the fields
    fields = ["Area No Data", "Area Degraded", "Area Stable", "Area Improved"]

    # multiply pixel area by the area which experienced each of the five transitions --> output: area in ha
    stats = te_prod.eq([-32768, -2, 0, 2]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    
    # Note that there may be multiple features
    out = []
    for p in [feature['properties'] for feature in stats.getInfo()['features']]:
        areas = {}
        total_area = sum(p.values())
        out.append({key: value/total_area for key,value in p.iteritems()})
    return out

d = get_degradation_areas(sys.argv[1])

#sys.stdout.write(json.dumps(d, ensure_ascii=False, indent=4))
sys.stdout.write(json.dumps(d, ensure_ascii=False))
