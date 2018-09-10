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

aoi = ee.Geometry(json.loads(sys.argv[1]))

out = {}

# s2_03: Main livelihoods
liv = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/livelihoodzones")

livImage = liv.filter(ee.Filter.neq('lztype_num', None)).reduceToImage(properties=['lztype_num'], reducer=ee.Reducer.first())

fields = ["Agro-Forestry", "Agro-Pastoral", "Arid", "Crops - Floodzone", "Crops - Irrigated", "Crops - Rainfed", "Fishery", "Forest-Based", "National Park", "Other", "Pastoral", "Urban"]
# multiply pixel area by the area which experienced each of the five transitions --> output: area in ha
livelihoodareas = livImage.eq([1,2,3,4,5,6,7,8,9,10,11,12]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum(),30)
out['livelihoods'] = get_fc_properties(livelihoodareas, normalize=True, scaling=100)

sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
