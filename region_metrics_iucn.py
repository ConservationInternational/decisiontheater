# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

from common import get_fc_properties, get_fc_properties_text, get_coords

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)

aoi = ee.Geometry.MultiPolygon(get_coords(json.loads(sys.argv[1])))

out = {}

###########################################################
# s4_03: degradation analysis within species ranges

# load productivity degradation
te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis") \
        .remap([-32768, 1, 2, 3, 4, 5, 6, 7], [-32768, -1, -1, 0, 0, 0, 1, 1])

# define the names of the fields
fields = ["nodata","decline","stable","improvement"]

# load mammals ranges (previously dissolved)
mammals_rng = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/terrestrial_mammals_dis")
mammals_deg = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/terrestrial_mammals_dis_degradation")

# filter only species intersecting the aoi and only selecting critically endangered (CR), endangered (EN) or vulnerable (VU)
mammals_rng_aoi = mammals_rng.filterBounds(aoi).filter(ee.Filter.Or(ee.Filter.eq('code',"CR"), ee.Filter.eq('code',"EN"), ee.Filter.eq('code',"VU")))
mammals_deg_all = mammals_deg.filterBounds(aoi).filter(ee.Filter.Or(ee.Filter.eq('code',"CR"), ee.Filter.eq('code',"EN"), ee.Filter.eq('code',"VU")))

# function to compute the intersection (clip) of species ranges to the aoi
def f_clip_ranges(feature):
    return feature.intersection(aoi, ee.ErrorMargin(1))

# apply function to feature collection with he ranges
mammals_clp = mammals_rng_aoi.map(f_clip_ranges)

# multiply pixel area by the area which experienced each of the three transitions --> output: area in ha
mammals_deg_aoi = te_prod.eq([-32768,-1,0,1]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(mammals_clp, ee.Reducer.sum())


# degradation stats per species within aoi
iucn_deg_aoi = get_fc_properties_text(mammals_deg_aoi)
iucn_deg_all = get_fc_properties_text(mammals_deg_all)

# Ranges stats ontains the attributes from the ranges + the three fields with 
# area in has of improved, decline or stable productivity. Clean up the 
# degradation statistics from GEE so they are percentages of the total area.
def clean_iucn_degradation(d):
    nodata = d.pop('nodata')
    degraded = d.pop('decline')
    stable = d.pop('stable')
    improved = d.pop('improvement')

    total = stable + degraded + improved + nodata

    d['degradation'] = {'nodata': nodata / total * 100,
                        'degraded': degraded / total * 100,
                        'stable': stable / total * 100,
                        'improved': improved / total * 100}
    return d
iucn_deg_aoi  = [clean_iucn_degradation(i) for i in iucn_deg_aoi]
iucn_deg_all = [clean_iucn_degradation(i) for i in iucn_deg_all]

# Now combine the two lists together so each species has a percent area 
# degraded in its range, and a percent area degraded in the aoi
iucn_deg = iucn_deg_aoi
for item in iucn_deg:
    entire_range = [s for s in iucn_deg_all if s['binomial'] == item['binomial']][0]
    item['degradation'] = {'aoi': item['degradation'],
                           'entire range': entire_range['degradation']}
out['iucn_mammals'] = iucn_deg

# Return all output as json on stdout
sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
