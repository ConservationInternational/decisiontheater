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
fc_loss = hansen.select('treecover2000').gte(tree_cover) \
        .And(hansen.select('lossyear').gt(year_start - 2000)) \
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
population = pop_cnt.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=1000, maxPixels=1e13).getInfo()['population-count']
out['population'] = population

# s3_01: SDG 15.3.1 degradation classes 

te_sdgi = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_sdg1531_gpg_globe_2001_2015_modis")
sdg_areas = te_sdgi.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
out['area_sdg'] = get_fc_properties(sdg_areas, normalize=True, scaling=100)

###########################################################/
# Restoration projections
# 1) Agriculture: Estimate economic benefit of reducing yield gaps in degraded agricultural lands by 50 % and of improving SOC by 6% over 30 years
# 2) Forest restoration: Estimate the C and $ benefit of bringing forest AGB to maximum in the area (95 percentile) over 30 years
# 3) Forest re-establishment: Estimate the C and $ benefit of regenerating forests in areas where forest has been lost
#
out['interventions'] = {'forest restoration': {},
                        'forest re-establishment': {},
                        'agricultural restoration': {}}

# load productivity degradation layer, and focus only on degradation classes: decline and early signs of decline
lp7cl = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis")

# load land cover: using 20 m land cover for 2016 for africa and 300 m 2015 for 
# the rest of the world
landc_300 = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015") \
        .select("lc_tg").remap([1,2,3,4,5,6,7],[1,3,4,5,8,7,10]) \
        .select(["remapped"],["b1"])

# 20 m land cover for africa from esa cci
landc_020 = ee.Image("users/marianogr80/ESACCI-LC-L4-LC10-Map-20m-P1Y-2016-v10")

# combine both datasets and display
landc = ee.ImageCollection([landc_300.int8(),landc_020.int8()]).mosaic()

# load yield gaps (source: http:#www.earthstat.org/data-download/)
yg_barle = ee.Image("users/geflanddegradation/yieldgap_earthstat/barley_yieldgap").unmask(0)
yg_groun = ee.Image("users/geflanddegradation/yieldgap_earthstat/groundnut_yieldgap").unmask(0)
yg_maize = ee.Image("users/geflanddegradation/yieldgap_earthstat/maize_yieldgap").unmask(0)
yg_rice0 = ee.Image("users/geflanddegradation/yieldgap_earthstat/rice_yieldgap").unmask(0)
yg_soybe = ee.Image("users/geflanddegradation/yieldgap_earthstat/soybean_yieldgap").unmask(0)
yg_sunfl = ee.Image("users/geflanddegradation/yieldgap_earthstat/sunflower_yieldgap").unmask(0)
yg_wheat = ee.Image("users/geflanddegradation/yieldgap_earthstat/wheat_yieldgap").unmask(0)

# potential yield (source: http:#www.earthstat.org/data-download/)
yp_barle = ee.Image("users/geflanddegradation/yieldgap_earthstat/barley_yieldpotential").unmask(0)
yp_groun = ee.Image("users/geflanddegradation/yieldgap_earthstat/groundnut_yieldpotential").unmask(0)
yp_maize = ee.Image("users/geflanddegradation/yieldgap_earthstat/maize_yieldpotential").unmask(0)
yp_rice0 = ee.Image("users/geflanddegradation/yieldgap_earthstat/rice_yieldpotential").unmask(0)
yp_soybe = ee.Image("users/geflanddegradation/yieldgap_earthstat/soybean_yieldpotential").unmask(0)
yp_sunfl = ee.Image("users/geflanddegradation/yieldgap_earthstat/sunflower_yieldpotential").unmask(0)
yp_wheat = ee.Image("users/geflanddegradation/yieldgap_earthstat/wheat_yieldpotential").unmask(0)

# harvested fraction (source: http:#www.earthstat.org/data-download/)
hf_barle = ee.Image("users/geflanddegradation/yieldgap_earthstat/barley_HarvestedAreaFraction").unmask(0)
hf_groun = ee.Image("users/geflanddegradation/yieldgap_earthstat/groundnut_HarvestedAreaFraction").unmask(0)
hf_maize = ee.Image("users/geflanddegradation/yieldgap_earthstat/maize_HarvestedAreaFraction").unmask(0)
hf_rice0 = ee.Image("users/geflanddegradation/yieldgap_earthstat/rice_HarvestedAreaFraction").unmask(0)
hf_soybe = ee.Image("users/geflanddegradation/yieldgap_earthstat/soybean_HarvestedAreaFraction").unmask(0)
hf_sunfl = ee.Image("users/geflanddegradation/yieldgap_earthstat/sunflower_HarvestedAreaFraction").unmask(0)
hf_wheat = ee.Image("users/geflanddegradation/yieldgap_earthstat/wheat_HarvestedAreaFraction").unmask(0)
hf_total = hf_barle.add(hf_groun.add(hf_maize.add(hf_rice0.add(hf_soybe.add(hf_sunfl.add(hf_wheat))))))

# potential vegetation cover from Hengl 2018 https:#dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/QQHCIK
pot_vegeta = ee.Image("users/geflanddegradation/pnv_biometype_biome00k_c_1km_s00cm_20002017_v01")
# define areas of potential forest vegetation cover
pot_forest = pot_vegeta.remap([1, 2, 3, 4, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20, 22, 27, 28, 30, 31, 32],
                              [1, 1, 1, 1, 1, 1, 1,  1,  1,  1,  1,  1,  1,  1,  0,  0,  0,  0,  0,  0,  0])

# Number	Original_biome_classification
# 1	tropical evergreen broadleaf forest
# 2	tropical semi-evergreen broadleaf forest
# 3	tropical deciduous broadleaf forest and woodland
# 4	warm-temperate evergreen broadleaf and mixed forest
# 7	wet sclerophyll forest
# 8	cool evergreen needleleaf forest
# 9	cool mixed forest
# 13	temperate deciduous broadleaf forest
# 14	cold deciduous forest
# 15	cold evergreen needleleaf forest
# 16	temperate sclerophyll woodland and shrubland
# 17	temperate evergreen needleleaf open woodland
# 18	tropical savanna
# 19	temperate deciduous broadleaf savanna
# 20	tropical xerophytic shrubland
# 22	tropical grassland
# 27	desert
# 28	graminoid and forb tundra
# 30	erect dwarf-shrub tundra
# 31	low and high shrub tundra
# 32	prostrate dwarf-shrub tundra

# key biodiversity area
kbas = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/KBAsGlobal_2018_01")

# convert to raster
kba_r = kbas.reduceToImage(properties=['OBJECTID'], reducer=ee.Reducer.first()).gte(0)

# protected areas
pas = ee.FeatureCollection("WCMC/WDPA/current/polygons")

# convert to raster
pas_r = pas.reduceToImage(properties=['METADATAID'], reducer=ee.Reducer.first()).gte(0)

# population from GPW4
pop_cnt = ee.Image("CIESIN/GPWv4/unwpp-adjusted-population-count/2015")

###########################################################/
# define areas for each of the 3 potential restoration activities

# for agriculture restoration: ag land cover, prod degradation, no kbas, no pas
r01_ag_resto = lp7cl.remap([-32768, 1, 2, 3, 4, 5, 6, 7],
                           [     0, 1, 1, 0, 0, 0, 0, 0]).eq(1).And(landc.eq(4)).where(kba_r.eq(1), 0).where(pas_r.eq(1), 0)
r01_ag_resto_area = r01_ag_resto.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e13).get("remapped")
out['interventions']['agricultural restoration']['area_hectares'] = r01_ag_resto_area.getInfo()

# for forest re-establishment: shrub, grass, sparce or other land cover in areas of potential forest (regardless of kbas or pas)
r02_fr_reest = pot_forest.eq(1).And(landc.remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0])).eq(1)
r02_fr_reest_area = r02_fr_reest.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e13).get("remapped")
out['interventions']['forest re-establishment']['area_hectares'] = r02_fr_reest_area.getInfo()

# for forest restoration: current degraded forests  (regardless of kbas or pas)
r03_fr_resto = lp7cl.remap([-32768, 1, 2, 3, 4, 5, 6, 7], [0, 1, 1, 0, 0, 0, 0, 0]).eq(1).And(landc.eq(1))
r03_fr_resto_area = r03_fr_resto.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e13).get("remapped")
out['interventions']['forest restoration']['area_hectares'] = r03_fr_resto_area.getInfo()

###########################################################/
# ag restoration calculation
###########################################################/
def f_crop_inc(ygap, ypot, hfra):
    crop_gap = (ypot.multiply(0.75).subtract(ypot.subtract(ygap))).divide(10000).updateMask(r01_ag_resto)
    crop_area = crop_gap.gt(0).multiply(ee.Image.pixelArea()).multiply(hfra.divide(hf_total)) \
            .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=20, maxPixels=1e13).get("b1")
    crop_mean = crop_gap.where(crop_gap.lt(0),0) \
            .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e13).get("b1")
    if crop_mean.getInfo() < 0:
        crop_mean = 0
    return ee.Number(crop_area).multiply(crop_mean)
  
# make function to work with tons, and mulitply by price at the end so I can get tons and money from same function ( remove margin from eq, leave reduction in yield gap)
barle_ton = f_crop_inc(yg_barle, yp_barle, hf_barle)
groun_ton = f_crop_inc(yg_groun, yp_groun, hf_groun)
maize_ton = f_crop_inc(yg_maize, yp_maize, hf_maize)
rice0_ton = f_crop_inc(yg_rice0, yp_rice0, hf_rice0)
soybe_ton = f_crop_inc(yg_soybe, yp_soybe, hf_soybe)
sunfl_ton = f_crop_inc(yg_sunfl, yp_sunfl, hf_sunfl)
wheat_ton = f_crop_inc(yg_wheat, yp_wheat, hf_wheat)

# prices from online sources in tons/ha and profit margins of 15% (https:#www.farmafrica.org/downloads/resources/MATFGrantholders-Report.5.pdf) 
barle_inc = barle_ton.multiply(130) # 130 $/ton 
groun_inc = groun_ton.multiply(1200)# 1200 $/ton
maize_inc = maize_ton.multiply(180) # 180 $/ton
rice0_inc = rice0_ton.multiply(380) # 380 $/ton
soybe_inc = soybe_ton.multiply(300) # 300 $/ton
sunfl_inc = sunfl_ton.multiply(780) # 780 $/ton
wheat_inc = wheat_ton.multiply(200) # 200 $/ton

total_inc = barle_inc.add(groun_inc.add(maize_inc.add(rice0_inc.add(soybe_inc.add(sunfl_inc.add(wheat_inc))))))
total_ton = barle_ton.add(groun_ton.add(maize_ton.add(rice0_ton.add(soybe_ton.add(sunfl_ton.add(wheat_ton))))))

perso_inc = total_inc.divide(population)

#Import SOC (ton/Ha)
soc = ee.Image("users/geflanddegradation/toolbox_datasets/soc_sgrid_30cm_unccd_20180111")
soc_ag_rest = ee.Number(soc.updateMask(r01_ag_resto) \
        .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e13).get("b1"))
if soc_ag_rest.getInfo() < 0:
    soc_ag_rest = ee.Number(0)

# rate of soc increase https:#www.dpi.nsw.gov.au/__data/assets/pdf_file/0014/321422/A-farmers-guide-to-increasing-Soil-Organic-Carbon-under-pastures.pdf
out['interventions']['agricultural restoration']['co2_tons_per_yr'] = soc_ag_rest.multiply(r01_ag_resto_area).multiply(0.06*3.67/30).getInfo()
out['interventions']['agricultural restoration']['dollars_per_psn_per_yr'] = soc_ag_rest.multiply(r01_ag_resto_area).multiply(0.06*3.67*15./30).divide(population).add(perso_inc).getInfo()

###########################################################/
# forest re-establishment calculation
###########################################################/

#Import biomass dataset: WHRC is Megagrams of Aboveground Live Woody Biomass per Hectare (ton/Ha)
agb = ee.Image("users/geflanddegradation/toolbox_datasets/forest_agb_30m_woodhole")

# calculate average above and below ground biomass Mokany et al. 2006 (convert to co2 eq totalcarbon * 3.67)
bgb = agb.expression('0.489 * BIO**(0.89)', {'BIO': agb})

# Calculate Total biomass (t/ha) then convert to carbon equilavent (*0.5) to get Total Carbon (t ha-1) = (AGB+BGB)*0.5
tco2 = agb.expression('(bgb + abg ) * 0.5 * 3.67 ', {'bgb': bgb,'abg': agb})

# define potential forest C stock (in co2 eq) as the 75th percentile of current forest stands in the area (added buffer in case there is no forest)
tco2_75pc = ee.Number(tco2.reduceRegion(reducer=ee.Reducer.percentile([75]), geometry=aoi.buffer(10000), scale=30, maxPixels=1e13).get("constant"))
if tco2_75pc.getInfo() < 0:
    tco2_75pc = ee.Number(0)

# define potential forest C stock (in co2 eq) as the 95th percentile of current forest stands in the area (added buffer in case there is no forest)
tco2_95pc = ee.Number(tco2.reduceRegion(reducer=ee.Reducer.percentile([95]), geometry=aoi.buffer(10000), scale=30, maxPixels=1e13).get("constant"))
if tco2_95pc.getInfo() < 0:
    tco2_95pc = ee.Number(0)

r03_fr_resto_co2_dif = tco2.subtract(ee.Number(tco2_95pc)).multiply(-1)#.updateMask(r03_fr_resto)

r03_fr_resto_co2_dif_mean = ee.Number(r03_fr_resto_co2_dif.where(r03_fr_resto_co2_dif.lt(0), 0)\
        .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20,  maxPixels=1e13).get("constant"))
if r03_fr_resto_co2_dif_mean.getInfo() < 0:
    r03_fr_resto_co2_dif_mean = ee.Number(0)

##########
# price of CO2 in USD/ton 15 source: http:#calcarbondash.org/
# forest re-establishment

out['interventions']['forest re-establishment']['co2_tons_per_yr'] = tco2_75pc.multiply(ee.Number(r02_fr_reest_area).divide(30)).getInfo()
out['interventions']['forest re-establishment']['dollars_per_psn_per_yr'] = tco2_75pc.multiply(ee.Number(r02_fr_reest_area)).multiply(15./30).divide(population).getInfo()

# forest restoration 
out['interventions']['forest restoration']['co2_tons_per_yr'] = r03_fr_resto_co2_dif_mean.multiply(ee.Number(r03_fr_resto_area).divide(30)).getInfo()
out['interventions']['forest restoration']['dollars_per_psn_per_yr'] = r03_fr_resto_co2_dif_mean.multiply(ee.Number(r03_fr_resto_area)).multiply(15./30).divide(population).getInfo()

# Cost of re-establishment over 30 years 900$/ha for planting 400$/ha natural regeneration over a 30 yr period
# Cost of forest regeneration in forest areas 1/2 of in ag land 200 $/ha  over a 30 yr period

sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
