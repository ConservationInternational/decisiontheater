# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

from common import get_fc_properties, get_coords, GEECall, get_pop, \
    get_area_sdg, get_ecosystem_service_dominant, get_ecosystem_service_value

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)

aoi = ee.Geometry.MultiPolygon(get_coords(json.loads(sys.argv[1])))

out = {}
out['interventions'] = {'forest restoration': {},
                        'forest re-establishment': {},
                        'agricultural intensification': {},
                        'agricultural expansion': {}}

threads = []

co2_dollar_per_ton = 50

###############################################################################
# General statistics on polygon

# polygon area in hectares
aoi_area = aoi.area().divide(10000).getInfo()
out['area_hectares'] = aoi_area

# To keep processing times reasonable, use a 300 m scale for calculations if 
# the area of the polygon is greater than 20,000 ha
if aoi_area < 5000:
    scale = 20
else:
    scale = 300
MAX_PIXELS= 1e9

# Need the population value, so need to wait on this thread
pop_thread = GEECall(get_pop, out, aoi)
pop_thread.join()
population = out['population']

threads.append(GEECall(get_area_sdg, out, aoi))

def get_forest_loss(out):
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
    forest_loss = get_fc_properties(areas.reduceRegions(collection=aoi, reducer=ee.Reducer.sum(), scale=scale),
                                    normalize=False)
    out['forest_loss'] = forest_loss['sum']
threads.append(GEECall(get_forest_loss, out))

###########################################################/
# Restoration projections
# 1) Agriculture: Estimate economic benefit of reducing yield gaps in degraded agricultural lands by 50 % and of improving SOC by 6% over 30 years
# 2) Forest restoration: Estimate the C and $ benefit of bringing forest AGB to maximum in the area (95 percentile) over 30 years
# 3) Forest re-establishment: Estimate the C and $ benefit of regenerating forests in areas where forest has been lost

# load productivity degradation layer, and focus only on degradation classes: 
# decline and early signs of decline
lp7cl = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis")

# load land cover: using 20 m land cover for 2016 for africa and 300 m 2015 for 
# the rest of the world
landc_300 = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015") \
        .select("lc_tg").remap([1,2,3,4,5,6,7],[1,3,4,5,8,7,10]) \
        .select(["remapped"],["b1"])

# 20 m land cover for africa from esa cci
landc_020 = ee.Image("users/marianogr80/ESACCI-LC-L4-LC10-Map-20m-P1Y-2016-v10")

# combine both datasets and display
landc = ee.ImageCollection([landc_300.int8(), landc_020.int8()]).mosaic()

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
pot_vegeta = ee.Image("users/geflanddegradation/toolbox_datasets/pnv_biometype_biome00k_c_1km_s00cm_20002017_v01")
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

#Import SOC (ton/Ha)
soc = ee.Image("users/geflanddegradation/toolbox_datasets/soc_sgrid_30cm_unccd_20180111")

###############################################################################
# define areas for each of the 3 potential restoration activities
###############################################################################

# for agriculture restoration: ag land cover, prod degradation, no kbas, no pas
ag_intens_r = lp7cl.remap([-32768, 1, 2, 3, 4, 5, 6, 7],
                           [     0, 1, 1, 0, 0, 0, 0, 0]) \
        .eq(1).And(landc.eq(4)).where(kba_r.eq(1), 0).where(pas_r.eq(1), 0)
ag_intens_area = ag_intens_r.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, 
                      maxPixels=MAX_PIXELS, bestEffort=True) \
        .get("remapped")
out['interventions']['agricultural intensification']['area_hectares'] = ag_intens_area.getInfo()
out['interventions']['agricultural intensification']['area_habitat_hectares'] = 0

# agriculture expansion: convert shrub, grass and sparce vegetation areas to 
# ag, no kbas, no pas
ag_expan_r = landc.remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                           [0, 0, 1, 1, 0, 0, 1, 0, 0, 0,  0]) \
        .eq(1).where(kba_r.eq(1), 0).where(pas_r.eq(1), 0)
ag_expan_area = ag_expan_r.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale,
                      maxPixels=MAX_PIXELS, bestEffort=True) \
        .get("remapped")
out['interventions']['agricultural expansion']['area_hectares'] = ag_expan_area.getInfo()
out['interventions']['agricultural expansion']['area_habitat_hectares'] = 0

# for forest re-establishment: shrub, grass, sparce or other land cover in areas of potential forest (regardless of kbas or pas)
for_reest_r = pot_forest.eq(1).And(landc.remap([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0])).eq(1)
for_reest_area = for_reest_r.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("remapped")
out['interventions']['forest re-establishment']['area_hectares'] = for_reest_area.getInfo()
#TODO: Fix so habitat is negative
out['interventions']['forest re-establishment']['area_habitat_hectares'] = for_reest_area.getInfo()

# for forest restoration: current degraded forests  (regardless of kbas or pas)
for_restor_r = lp7cl.remap([-32768, 1, 2, 3, 4, 5, 6, 7], [0, 1, 1, 0, 0, 0, 0, 0]).eq(1).And(landc.eq(1))
for_restor_area = for_restor_r.multiply(ee.Image.pixelArea().divide(10000)) \
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("remapped")
out['interventions']['forest restoration']['area_hectares'] = for_restor_area.getInfo()
out['interventions']['forest restoration']['area_habitat_hectares'] = for_restor_area.getInfo()

def get_ag_intens(out):
    def f_crop_inc_intensification(ygap, ypot, hfra):
        crop_gap = (ypot.multiply(0.75).subtract(ypot.subtract(ygap))).divide(10000).updateMask(ag_intens_r)
        crop_area = crop_gap.gt(0).multiply(ee.Image.pixelArea()).multiply(hfra.divide(hf_total)) \
                .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1")
        crop_mean = crop_gap.where(crop_gap.lt(0),0) \
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1")
        if crop_mean.getInfo() < 0:
            crop_mean = ee.Number(0)
        return ee.Number(crop_area).multiply(crop_mean)
      
    # make function to work with tons, and mulitply by price at the end so I can get tons and money from same function ( remove margin from eq, leave reduction in yield gap)
    barle_ton = f_crop_inc_intensification(yg_barle, yp_barle, hf_barle)
    groun_ton = f_crop_inc_intensification(yg_groun, yp_groun, hf_groun)
    maize_ton = f_crop_inc_intensification(yg_maize, yp_maize, hf_maize)
    rice0_ton = f_crop_inc_intensification(yg_rice0, yp_rice0, hf_rice0)
    soybe_ton = f_crop_inc_intensification(yg_soybe, yp_soybe, hf_soybe)
    sunfl_ton = f_crop_inc_intensification(yg_sunfl, yp_sunfl, hf_sunfl)
    wheat_ton = f_crop_inc_intensification(yg_wheat, yp_wheat, hf_wheat)

    # prices from online sources in tons/ha and profit margins of 15% (https:#www.farmafrica.org/downloads/resources/MATFGrantholders-Report.5.pdf) 
    barle_inc = barle_ton.multiply(130) # 130 $/ton 
    groun_inc = groun_ton.multiply(1200)# 1200 $/ton
    maize_inc = maize_ton.multiply(180) # 180 $/ton
    rice0_inc = rice0_ton.multiply(380) # 380 $/ton
    soybe_inc = soybe_ton.multiply(300) # 300 $/ton
    sunfl_inc = sunfl_ton.multiply(780) # 780 $/ton
    wheat_inc = wheat_ton.multiply(200) # 200 $/ton

    ag_intens_crop_value = barle_inc.add(groun_inc.add(maize_inc.add(rice0_inc.add(soybe_inc.add(sunfl_inc.add(wheat_inc))))))

    soc_ag_rest = ee.Number(soc.updateMask(ag_intens_r) \
            .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1"))
    if soc_ag_rest.getInfo() < 0:
        soc_ag_rest = ee.Number(0)

    ag_intens_co2 = soc_ag_rest.multiply(ag_intens_area).multiply(0.06*3.67/30) # co2 ag intensification (ton/year)
    ag_intens_co2_value = ag_intens_co2.multiply(co2_dollar_per_ton) # co2 ag intensification (usd/year)
    ag_intens_value = ag_intens_crop_value.add(ag_intens_co2_value)
    ag_intens_cost = ag_intens_crop_value.divide(1.15)
    ag_intens_benef = (ag_intens_value.subtract(ag_intens_cost)).divide(population)

    # rate of soc increase https:#www.dpi.nsw.gov.au/__data/assets/pdf_file/0014/321422/A-farmers-guide-to-increasing-Soil-Organic-Carbon-under-pastures.pdf
    out['interventions']['agricultural intensification']['co2_tons_per_yr'] = ag_intens_co2.getInfo()
    out['interventions']['agricultural intensification']['dollars_benefits_total'] = ag_intens_value.getInfo()
    out['interventions']['agricultural intensification']['dollars_cost_total'] = ag_intens_cost.getInfo()
    out['interventions']['agricultural intensification']['dollars_net_per_psn_per_yr'] = ag_intens_benef.getInfo()
threads.append(GEECall(get_ag_intens, out))

def get_ag_expan(out):
    def f_crop_inc_expansion(ypot, hfra):
        crop_gap = ypot.multiply(0.75).divide(10000).updateMask(ag_expan_r)
        crop_area = crop_gap.gt(0).multiply(ee.Image.pixelArea()).multiply(hfra.divide(hf_total)) \
                .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1")
        crop_mean = crop_gap.where(crop_gap.lt(0), 0) \
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1")
        if crop_mean.getInfo() < 0:
            crop_mean = ee.Number(0)
        return ee.Number(crop_area).multiply(crop_mean)

    # make function to work with tons, and mulitply by price at the end so I can 
    # get tons and money from same function ( remove margin from eq, leave 
    # reduction in yield gap)
    barle_ton = f_crop_inc_expansion(yp_barle, hf_barle)
    groun_ton = f_crop_inc_expansion(yp_groun, hf_groun)
    maize_ton = f_crop_inc_expansion(yp_maize, hf_maize)
    rice0_ton = f_crop_inc_expansion(yp_rice0, hf_rice0)
    soybe_ton = f_crop_inc_expansion(yp_soybe, hf_soybe)
    sunfl_ton = f_crop_inc_expansion(yp_sunfl, hf_sunfl)
    wheat_ton = f_crop_inc_expansion(yp_wheat, hf_wheat)

    # prices from online sources in tons/ha and profit margins of 15% (https:#www.farmafrica.org/downloads/resources/MATFGrantholders-Report.5.pdf) 
    barle_inc = barle_ton.multiply(130) # 130 $/ton 
    groun_inc = groun_ton.multiply(1200)# 1200 $/ton
    maize_inc = maize_ton.multiply(180) # 180 $/ton
    rice0_inc = rice0_ton.multiply(380) # 380 $/ton
    soybe_inc = soybe_ton.multiply(300) # 300 $/ton
    sunfl_inc = sunfl_ton.multiply(780) # 780 $/ton
    wheat_inc = wheat_ton.multiply(200) # 200 $/ton

    ag_expan_crop_value = barle_inc.add(groun_inc.add(maize_inc.add(rice0_inc.add(soybe_inc.add(sunfl_inc.add(wheat_inc))))))

    soc_ag_exp = ee.Number(soc.updateMask(ag_expan_r) \
            .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=MAX_PIXELS, bestEffort=True).get("b1"))
    if soc_ag_exp.getInfo() < 0:
        soc_ag_exp = ee.Number(0)

    # mean rate of soc loss from conversion of grassland to ag from trends.earth 
    # 40% over 20 years
    ag_expan_co2 = soc_ag_exp.multiply(ag_expan_area).multiply(-0.4/20) # co2 ag expansion (ton/year)
    ag_expan_co2_value = ag_expan_co2.multiply(co2_dollar_per_ton) # co2 ag expansion (usd/year)

    ag_expan_value = ag_expan_crop_value.add(ag_expan_co2_value)
    ag_expan_cost = ag_expan_crop_value.divide(1.15)

    out['interventions']['agricultural expansion']['co2_tons_per_yr'] = ag_expan_co2.getInfo()
    out['interventions']['agricultural expansion']['dollars_net_per_psn_per_yr'] = ag_expan_value.subtract(ag_expan_cost).divide(population).getInfo()
    out['interventions']['agricultural expansion']['dollars_cost_total'] = ag_expan_cost.getInfo()
    out['interventions']['agricultural expansion']['dollars_benefits_total'] = ag_expan_value.getInfo()
threads.append(GEECall(get_ag_expan, out))

###############################################################################
# forest restoration/re-establishment cost calculations
###############################################################################

#Import biomass dataset: WHRC is Megagrams of Aboveground Live Woody Biomass per Hectare (ton/Ha)
agb = ee.Image("users/geflanddegradation/toolbox_datasets/forest_agb_30m_woodhole")

# calculate average above and below ground biomass Mokany et al. 2006 (convert to co2 eq totalcarbon * 3.67)
bgb = agb.expression('0.489 * BIO**(0.89)', {'BIO': agb})

# Calculate Total biomass (t/ha) then convert to carbon equilavent (*0.5) to get Total Carbon (t ha-1) = (AGB+BGB)*0.5
tco2 = agb.expression('(bgb + abg ) * 0.5 * 3.67 ', {'bgb': bgb,'abg': agb})

# define potential forest C stock (in co2 eq) as the 75th percentile of current forest stands in the area (added buffer in case there is no forest)
tco2_85pc = ee.Number(tco2.reduceRegion(reducer=ee.Reducer.percentile([85]), 
                                        geometry=aoi.buffer(10000), 
                                        scale=scale, maxPixels=MAX_PIXELS, 
                                        bestEffort=True).get("constant"))
if tco2_85pc.getInfo() < 0:
    tco2_85pc = ee.Number(0)

def get_for_restor(out):
    for_restor_co2_dif = tco2.subtract(ee.Number(tco2_85pc)).multiply(-1)
    for_restor_co2_dif_mean = ee.Number(for_restor_co2_dif.where(for_restor_co2_dif.lt(0), 0) \
            .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=scale,  maxPixels=MAX_PIXELS, bestEffort=True).get("constant"))
    if for_restor_co2_dif_mean.getInfo() < 0:
        for_restor_co2_dif_mean = ee.Number(0)

    # Note: price of CO2 in USD/ton 15 source: http:#calcarbondash.org/
    for_restor_co2 = for_restor_co2_dif_mean.multiply(ee.Number(for_restor_area).divide(20)) # co2 forest restoration (ton/year)
    for_restor_value = for_restor_co2.multiply(co2_dollar_per_ton) # co2 forest restoration (usd/year)
    for_restor_cost = ee.Number(for_restor_area).multiply(100)
    for_restor_net_benef = (for_restor_value.subtract(for_restor_cost)).divide(population)

    # forest restoration 
    out['interventions']['forest restoration']['co2_tons_per_yr'] = for_restor_co2.getInfo()
    out['interventions']['forest restoration']['dollars_net_per_psn_per_yr'] = for_restor_net_benef.getInfo()
    out['interventions']['forest restoration']['dollars_cost_total'] = for_restor_cost.getInfo()
    out['interventions']['forest restoration']['dollars_benefits_total'] = for_restor_value.getInfo()
threads.append(GEECall(get_for_restor, out))

def get_for_reest(out):
    # Cost of re-establishment over 30 years 900$/ha for planting 400$/ha 
    # natural regeneration over a 30 yr period
    # Cost of forest regeneration in forest areas 1/2 of in ag land 200 $/ha  over a 30 yr period
    for_reest_co2 = tco2_85pc.multiply(ee.Number(for_reest_area).divide(20)) # co2 forest re-establ (ton/year)
    for_reest_value = for_reest_co2.multiply(co2_dollar_per_ton) # co2 forest re-establ (usd/year)
    for_reest_cost = ee.Number(for_reest_area).multiply(400)
    for_reest_benef = (for_reest_value.subtract(for_reest_cost)).divide(population)

    out['interventions']['forest re-establishment']['co2_tons_per_yr'] = for_reest_co2.getInfo()
    out['interventions']['forest re-establishment']['dollars_net_per_psn_per_yr'] = for_reest_benef.getInfo()
    out['interventions']['forest re-establishment']['dollars_cost_total'] = for_reest_cost.getInfo()
    out['interventions']['forest re-establishment']['dollars_benefits_total'] = for_reest_value.getInfo()
threads.append(GEECall(get_for_reest, out))

threads.append(GEECall(get_ecosystem_service_dominant, out, aoi))

threads.append(GEECall(get_ecosystem_service_value, out, aoi))

for t in threads:
    t.join()
sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
