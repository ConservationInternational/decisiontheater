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

###############################################################################
# Carbon emissions calculations

# Minimun tree cover to be considered a forest
tree_cover = 30
year_start = 2001
year_end = 2015

##############################################/
# DATASETS
# Import Hansen global forest dataset
hansen = ee.Image('UMD/hansen/global_forest_change_2016_v1_4')

#Import biomass dataset: WHRC is Megagrams of Aboveground Live Woody Biomass per Hectare (Mg/Ha)
agb = ee.Image("users/geflanddegradation/toolbox_datasets/forest_agb_30m_woodhole")

# reclass to 1.broadleaf, 2.conifer, 3.mixed, 4.savanna
f_type = ee.Image("users/geflanddegradation/toolbox_datasets/esa_forest_expanded_2015") \
    .remap([50, 60, 61, 62, 70, 71, 72, 80, 81, 82, 90, 100, 110], 
           [ 1,  1,  1,  1,  2,  2,  2,  2,  2,  2,  3,   3,   3])

# IPCC climate zones reclassified as from http:#eusoils.jrc.ec.europa.eu/projects/RenewableEnergy/
# 0-No data, 1-Warm Temperate Moist, 2-Warm Temperate Dry, 3-Cool Temperate Moist, 4-Cool Temperate Dry, 5-Polar Moist,
# 6-Polar Dry, 7-Boreal Moist, 8-Boreal Dry, 9-Tropical Montane, 10-Tropical Wet, 11-Tropical Moist, 12-Tropical Dry) to
# 0: no data, 1:trop/sub moist, 2: trop/sub dry, 3: temperate)
climate = ee.Image("users/geflanddegradation/toolbox_datasets/ipcc_climate_zones") \
    .remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
           [0, 1, 2, 3, 3, 3, 3, 3, 3, 1,  1, 1, 2])

# Root to shoot ratio methods
# calculate average above and below ground biomass
# BGB (t ha-1) Citation Mokany et al. 2006 = (0.489)*(AGB)^(0.89)
# Mokany used a linear regression of root biomass to shoot biomass for 
# forest and woodland and found that BGB(y) is ~ 0.489 of AGB(x).  
# However, applying a power (0.89) to the shoot data resulted in an improved model 
# for relating root biomass (y) to shoot biomass (x):
# y = 0:489 x0:890
bgb = agb.expression('0.489 * BIO**(0.89)', {'BIO': agb})
rs_ratio = agb.divide(bgb)

# Calculate Total biomass (t/ha) then convert to carbon equilavent (*0.5) to get Total Carbon (t ha-1) = (AGB+BGB)*0.5
tbcarbon = agb.expression('(bgb + abg ) * 0.5 ', {'bgb': bgb,'abg': agb})

# convert Total Carbon to Total Carbon dioxide tCO2/ha 
# One ton of carbon equals 44/12 = 11/3 = 3.67 tons of carbon dioxide
teco2 = agb.expression('totalcarbon * 3.67 ', {'totalcarbon': tbcarbon})

##############################################/
# define forest cover at the starting date
fc_str = ee.Image(1).updateMask(hansen.select('treecover2000').gte(tree_cover)) \
    .updateMask(hansen.select('lossyear').where(hansen.select('lossyear').eq(0),9999).gte(year_start - 2000 + 1)) \
    .rename(['forest_cover_{}'.format(year_start)])

# using forest cover at the start year, identify losses per year
fl_stack = ee.Image().select()
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  fl = fc_str.updateMask(hansen.select('lossyear').eq(k)).rename(['forest_loss_hectares_{}'.format(k + 2000)])
  fl_stack = fl_stack.addBands(fl)

# use the losses per year to compute forest extent per year
fc_stack = fc_str
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  fc =  fc_stack.select('forest_cover_{}'.format(k + 2000 - 1)).updateMask(fl_stack.select('forest_loss_hectares_{}'.format(k + 2000)).unmask(0).neq(1)).rename(['forest_cover_{}'.format(k + 2000)])
  fc_stack = fc_stack.addBands(fc)

# use annual forest extent to estimate annual forest biomass in tons C/ha
cb_stack = ee.Image().select()
for k in range(year_start - 2000, year_end - 2000 + 1):
  cb =  tbcarbon.updateMask(fc_stack.select('forest_cover_{}'.format(k + 2000)).eq(1)).rename(['carbon_biomass_tons_per_ha_{}'.format(k + 2000)])
  cb_stack = cb_stack.addBands(cb)

# use annual forest loss to estimate annual emissions from deforestation in tons CO2/ha
ce_stack = ee.Image().select()
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  ce =  teco2.updateMask(fl_stack.select('forest_loss_hectares_{}'.format(k + 2000)).eq(1)).rename(['carbon_emissions_tons_co2e_{}'.format(k + 2000)])
  ce_stack = ce_stack.addBands(ce)

# combine all the datasets into a multilayer stack
output = fc_stack.addBands(fl_stack).addBands(cb_stack).addBands(ce_stack)

# compute pixel areas in hectareas
areas =  output.multiply(ee.Image.pixelArea().divide(10000))

# Get annual emissions and sum them across all years
emissions = get_fc_properties(areas.reduceRegions(collection=aoi, reducer=ee.Reducer.sum(), scale=30),
        normalize=False, filter_regex='carbon_emissions_tons_co2e_[0-9]*')
out['carbon_emissions_tons_co2e'] = sum(emissions.values())

forest_areas = get_fc_properties(areas.reduceRegions(collection=aoi, reducer=ee.Reducer.sum(), scale=30),
        normalize=False, filter_regex='forest_cover_[0-9]*')

out['forest_area_hectares_2001'] = forest_areas['forest_cover_2001']
out['forest_area_hectares_2015'] = forest_areas['forest_cover_2015']

# Return all output as json on stdout
sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
