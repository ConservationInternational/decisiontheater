# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

from common import fc_areas_to_pct_dict

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)

aoi = ee.Geometry(json.loads(sys.argv[1]))

out = {}

# polygon area in hectares
out['area'] = aoi.area().divide(10000).getInfo()

# s2_02: Number of people living inside the polygon in 2015
pop_cnt = ee.Image("CIESIN/GPWv4/unwpp-adjusted-population-count/2015")
population = pop_cnt.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=1000, maxPixels=1e9)
out['population'] = population.getInfo()['population-count']

# s2_03: Main livelihoods
liv = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/livelihoodzones")

livImage = liv.filter(ee.Filter.neq('lztype_num', None)).reduceToImage(properties=['lztype_num'], reducer=ee.Reducer.first())

fields = ["Agro-Forestry", "Agro-Pastoral", "Arid", "Crops - Floodzone", "Crops - Irrigated", "Crops - Rainfed", "Fishery", "Forest-Based", "National Park", "Other", "Pastoral", "Urban"]
# multiply pixel area by the area which experienced each of the five transitions --> output: area in ha
livelihoodareas = livImage.eq([1,2,3,4,5,6,7,8,9,10,11,12]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum(),30)
out['livelihoods'] = fc_areas_to_pct_dict(livelihoodareas)


# s3_01: SDG 15.3.1 degradation classes 

te_sdgi = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_sdg1531_gpg_globe_2001_2015_modis")
sdg_areas = te_sdgi.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_sdg'] = fc_areas_to_pct_dict(sdg_areas)

# s3_02: Productivity degradation classes
te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis").remap([-32768,1,2,3,4,5,6,7],[-32768,-1,-1,0,0,0,1,1])
prod_areas = te_prod.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_prod'] = fc_areas_to_pct_dict(prod_areas)

# s3_03: Land cover degradation classes
te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015")
lc_areas = te_land.select("lc_dg").eq([-1,0,1]).rename(["degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_lc'] = fc_areas_to_pct_dict(lc_areas)

# s3_04: soc degradation classes
te_socc_deg = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_deg").select("soc_deg")
soc_areas = te_socc_deg.eq([-32768,-1,0,1]).rename(["no data", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_soc'] = fc_areas_to_pct_dict(soc_areas)


# s3_05: compute land cover classes for 2001 and 2015, and the transitions which occured
te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015").select("lc_tr")
te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis").remap([-32768,1,2,3,4,5,6,7],[-32768,-1,-1,0,0,0,1,1])

fields = ["nodata", "degraded", "stable", "improved"]

prod_forests = te_prod.updateMask(te_land.eq(11)).eq([-32768,-1,0,1]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['prod_forests'] = fc_areas_to_pct_dict(prod_forests)

prod_grasslands = te_prod.updateMask(te_land.eq(22)).eq([-32768,-1,0,1]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['prod_grasslands'] = fc_areas_to_pct_dict(prod_grasslands)

prod_agriculture = te_prod.updateMask(te_land.eq(33)).eq([-32768,-1,0,1]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['prod_agriculture'] = fc_areas_to_pct_dict(prod_forests)

# s3_06: compute land cover classes for 2001 and 2015, and the transitions which occured
te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015")

# field names for annual land covers
fields = ["forest", "grassland", "agriculture", "wetlands", "artificial", "other land-bare", "water"]

# multiply pixel area by the area which experienced each of the lc classes --> output: area in ha
lc_baseline = te_land.select("lc_bl").eq([1,2,3,4,5,6,7]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
# multiply pixel area by the area which experienced each of the lc classes --> output: area in ha
lc_target = te_land.select("lc_tg").eq([1,2,3,4,5,6,7]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())

out['lc_2001'] = fc_areas_to_pct_dict(lc_baseline)
out['lc_2015'] = fc_areas_to_pct_dict(lc_target)

# field names for land cover transitions between 2001-2015
fields = ["for-for", "for-gra", "for-agr", "for-wet", "for-art", "for-oth", "for-wat",
          "gra-for", "gra-gra", "gra-agr", "gra-wet", "gra-art", "gra-oth", "gra-wat",
          "agr-for", "agr-gra", "agr-agr", "agr-wet", "agr-art", "agr-oth", "agr-wat",
          "wet-for", "wet-gra", "wet-agr", "wet-wet", "wet-art", "wet-oth", "wet-wat",
          "art-for", "art-gra", "art-agr", "art-wet", "art-art", "art-oth", "art-wat",
          "oth-for", "oth-gra", "oth-agr", "oth-wet", "oth-art", "oth-oth", "oth-wat",
          "wat-for", "wat-gra", "wat-agr", "wat-wet", "wat-art", "wat-oth", "wat-wat"]

# multiply pixel area by the area which experienced each of the lc transition classes --> output: area in ha
lc_transitions = te_land.select("lc_tr").eq([11,12,13,14,15,16,17,21,22,23,24,25,26,26,31,32,33,34,35,36,37,41,42,43,44,45,46,47,51,52,53,54,55,56,57,
              61,62,63,64,65,66,67,71,72,73,74,75,76,77]).rename(fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['lc_transition'] = fc_areas_to_pct_dict(lc_transitions, normalize=False)

# s3_07: percent change in soc stocks between 2001-2015
soc_pch_img = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_deg").select("soc_pch")

# compute statistics for region
soc_pch = soc_pch_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=250, maxPixels=1e9)
# Multiple by 100 to convert to a percentage
out['soc_change_percent'] = soc_pch.getInfo()['soc_pch'] * 100
  
# s3_08: change in soc stocks in tons of co2 eq between 2001-2015
soc_an_img = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_annual_soc")

# compute change in SOC between 2001 and 2015 converted to co2 eq
soc_chg_an = (soc_an_img.select('y2015').subtract(soc_an_img.select('y2001'))).multiply(250*250/10000).multiply(3.67)
# compute statistics for the region
soc_chg_tons_co2e = soc_chg_an.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=250, maxPixels=1e9)
out['soc_change_tons_co2e'] = soc_chg_tons_co2e.getInfo()['y2015']



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
    .rename(['fc{}'.format(year_start)])

# using forest cover at the start year, identify losses per year
fl_stack = ee.Image().select()
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  fl = fc_str.updateMask(hansen.select('lossyear').eq(k)).rename(['fl{}'.format(k + 2000)])
  fl_stack = fl_stack.addBands(fl)

# use the losses per year to compute forest extent per year
fc_stack = fc_str
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  fc =  fc_stack.select('fc{}'.format(k + 2000 - 1)).updateMask(fl_stack.select('fl{}'.format(k + 2000)).unmask(0).neq(1)).rename(['fc{}'.format(k + 2000)])
  fc_stack = fc_stack.addBands(fc)

# use annual forest extent to estimate annual forest biomass in tons C/ha
cb_stack = ee.Image().select()
for k in range(year_start - 2000, year_end - 2000 + 1):
  cb =  tbcarbon.updateMask(fc_stack.select('fc{}'.format(k + 2000)).eq(1)).rename(['cb{}'.format(k + 2000)])
  cb_stack = cb_stack.addBands(cb)

# use annual forest loss to estimate annual emissions from deforestation in tons CO2/ha
ce_stack = ee.Image().select()
for k in range(year_start - 2000 + 1, year_end - 2000 + 1):
  ce =  teco2.updateMask(fl_stack.select('fl{}'.format(k + 2000)).eq(1)).rename(['ce{}'.format(k + 2000)])
  ce_stack = ce_stack.addBands(ce)

# combine all the datasets into a multilayer stack
output = fc_stack.addBands(fl_stack).addBands(cb_stack).addBands(ce_stack)

# compute pixel areas in hectareas
areas =  output.multiply(ee.Image.pixelArea().divide(10000))

# compute statistics for the regions
# stats = areas.reduceRegions(collection=aoi, reducer=ee.Reducer.sum(), scale=30)
# print stats.getInfo()

# The output table will have the attributes from the input table plus:
# cb2000-cb2016: annual forest above and below ground biomass in tons C/ha
# ce2001-ce2016: annual emissions from deforestation in tons CO2/ha
# fl2001-fl2016: annual forest loss in ha
# fc2000-fc2016: annual forest cover in ha

# Return all output as json on stdout

sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
#sys.stdout.write(json.dumps(d, ensure_ascii=False))
