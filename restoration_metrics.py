# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

from common import get_fc_properties

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)


# TODO: FIX THIS!
aoi = ee.Geometry(json.loads(sys.argv[1]))

print aoi.toGeoJSON()

out = {}

###############################################################################
# Forest gain/loss calculations

# Minimun tree cover to be considered a forest
tree_cover = 30
year_start = 2001
year_end = 2015

# Import Hansen global forest dataset
hansen = ee.Image('UMD/hansen/global_forest_change_2017_v1_5')

# define forest cover at the starting date
fc_loss = ee.Image(1).updateMask(hansen.select('treecover2000').gte(tree_cover)) \
    .updateMask(hansen.select('lossyear').where(hansen.select('lossyear').eq(0),9999).gte(year_start - 2000 + 1)) \
    .And(hansen.select('lossyear').gte(year_start - 2000 + 1)) \
    .And(hansen.select('lossyear').lte(year_end - 2000))

# compute pixel areas in hectareas
areas = fc_loss.multiply(ee.Image.pixelArea().divide(10000))
forest_loss = get_fc_properties(areas.reduceRegions(collection=aoi, reducer=ee.Reducer.sum(), scale=30),
                                normalize=False)
out['forest_loss'] = forest_loss['sum']

###############################################################################
# Other calculations

# polygon area in hectares
out['area_hectares'] = aoi.area().divide(10000).getInfo()

# s2_02: Number of people living inside the polygon in 2015
pop_cnt = ee.Image("CIESIN/GPWv4/unwpp-adjusted-population-count/2015")
population = pop_cnt.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=1000, maxPixels=1e9)
out['population'] = population.getInfo()['population-count']

# s3_01: SDG 15.3.1 degradation classes 

te_sdgi = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_sdg1531_gpg_globe_2001_2015_modis")
sdg_areas = te_sdgi.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_sdg'] = get_fc_properties(sdg_areas, normalize=True, scaling=100)

sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
