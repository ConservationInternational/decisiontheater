# Script to calculate statistics for a selected region for use by Decision
# Theater Trends.Earth visualization.
#
#  Takes a geojson as text as a command-line parameter, and returns values as
# JSON to standard out.

import sys
import json
import io

import ee

from common import get_fc_properties, get_coords, GEECall

service_account = 'gef-ldmp-server@gef-ld-toolbox.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'dt_key.json')
ee.Initialize(credentials)
#ee.Initialize()

MAX_PIXELS= 1e9

aoi = ee.Geometry.MultiPolygon(get_coords(json.loads(sys.argv[1])))

out = {}
threads = []

def get_area(out):
    # polygon area in hectares
    out['area_hectares'] = aoi.area().divide(10000).getInfo()
    return out
threads.append(GEECall(get_area, out))

def get_pop(out):
    # s2_02: Number of people living inside the polygon in 2015
    pop_cnt = ee.Image("CIESIN/GPWv4/unwpp-adjusted-population-count/2015")
    population = pop_cnt.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, 
                                      scale=1000, maxPixels=MAX_PIXELS, bestEffort=True)
    out['population'] = population.getInfo()['population-count']
    return out
threads.append(GEECall(get_pop, out))

def get_livelihoods(out):
    # s2_03: Main livelihoods
    liv = ee.FeatureCollection("users/geflanddegradation/toolbox_datasets/livelihoodzones")

    livImage = liv.filter(ee.Filter.neq('lztype_num', None)).reduceToImage(properties=['lztype_num'], reducer=ee.Reducer.first()).unmask(0)

    liv_fields = ["No Data", "Agro-Forestry", "Agro-Pastoral", "Arid", "Crops - Floodzone", "Crops - Irrigated", "Crops - Rainfed", "Fishery", "Forest-Based", "National Park", "Other", "Pastoral", "Urban"]
    # multiply pixel area by the area which experienced each of the five transitions --> output: area in ha
    livelihoodareas = livImage.eq([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) \
            .rename(liv_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum(), 250)
    out['livelihoods'] = get_fc_properties(livelihoodareas, normalize=True, scaling=100)
    # Handle the case of polygons outside of the area of coverage of the livelihood 
    # zones data
    if out['livelihoods']['No Data'] < 10:
        # If there is less than 10 percent no data, then ignore the no data by 
        # eliminating that category, and normalizing all the remaining categories 
        # to sum to 100
        out['livelihoods'].pop('No Data')
        denominator = sum(out['livelihoods'].values())
        out['livelihoods'] = {key: value / denominator * 100 for key, value in out['livelihoods'].iteritems()}
    else:
        # if more than 10% of the area is no data, then return zero for all 
        # categories
        out['livelihoods'].pop('No Data')
        out['livelihoods'] = {key: 0. for key, value in out['livelihoods'].iteritems()}
    return out
threads.append(GEECall(get_livelihoods, out))


def get_area_sdg(out):
    # s3_01: SDG 15.3.1 degradation classes 
    te_sdgi = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_sdg1531_gpg_globe_2001_2015_modis")
    sdg_areas = te_sdgi.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['area_sdg'] = get_fc_properties(sdg_areas, normalize=True, scaling=100)
threads.append(GEECall(get_area_sdg, out))

def get_area_prod(out):
    # s3_02: Productivity degradation classes
    te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis").remap([-32768,1,2,3,4,5,6,7],[-32768,-1,-1,0,0,0,1,1])
    prod_areas = te_prod.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['area_prod'] = get_fc_properties(prod_areas, normalize=True, scaling=100)
threads.append(GEECall(get_area_prod, out))

def get_area_lc(out):
    # s3_03: Land cover degradation classes
    te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015")
    lc_areas = te_land.select("lc_dg").eq([-1,0,1]).rename(["degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['area_lc'] = get_fc_properties(lc_areas, normalize=True, scaling=100)
threads.append(GEECall(get_area_lc, out))

def get_area_soc(out):
    # s3_04: soc degradation classes
    te_socc_deg = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_deg").select("soc_deg")
    soc_areas = te_socc_deg.eq([-32768,-1,0,1]).rename(["no data", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['area_soc'] = get_fc_properties(soc_areas, normalize=True, scaling=100)
threads.append(GEECall(get_area_soc, out))


prod_fields = ["nodata", "degraded", "stable", "improved"]

te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015").select("lc_tr")
te_prod = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lp7cl_globe_2001_2015_modis").remap([-32768,1,2,3,4,5,6,7],[-32768,-1,-1,0,0,0,1,1])

def get_prod_forests(out):
    prod_forests = te_prod.updateMask(te_land.eq(11)).eq([-32768,-1,0,1]).rename(prod_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['prod_forests'] = get_fc_properties(prod_forests, normalize=True, scaling=100)
threads.append(GEECall(get_prod_forests, out))

def get_prod_grasslands(out):
    prod_grasslands = te_prod.updateMask(te_land.eq(22)).eq([-32768,-1,0,1]).rename(prod_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['prod_grasslands'] = get_fc_properties(prod_grasslands, normalize=True, scaling=100)
threads.append(GEECall(get_prod_grasslands, out))

def get_prod_agriculture(out):
    prod_agriculture = te_prod.updateMask(te_land.eq(33)).eq([-32768,-1,0,1]).rename(prod_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['prod_agriculture'] = get_fc_properties(prod_agriculture, normalize=True, scaling=100)
threads.append(GEECall(get_prod_agriculture, out))

# s3_06: compute land cover classes for 2001 and 2015, and the transitions which occured
te_land = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_lc_traj_globe_2001-2001_to_2015")

# field names for annual land covers
lc_fields = ["forest", "grassland", "agriculture", "wetlands", "artificial", "other land-bare", "water"]

# multiply pixel area by the area which experienced each of the lc classes --> output: area in ha
lc_baseline = te_land.select("lc_bl").eq([1,2,3,4,5,6,7]).rename(lc_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
# multiply pixel area by the area which experienced each of the lc classes --> output: area in ha
lc_target = te_land.select("lc_tg").eq([1,2,3,4,5,6,7]).rename(lc_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())

def get_lc_2001(out):
    out['lc_2001'] = get_fc_properties(lc_baseline, normalize=True, scaling=100)
threads.append(GEECall(get_lc_2001, out))

def get_lc_2015(out):
    out['lc_2015'] = get_fc_properties(lc_target, normalize=True, scaling=100)
threads.append(GEECall(get_lc_2015, out))

# field names for land cover transitions between 2001-2015
lc_tr_fields = ["for-for", "for-gra", "for-agr", "for-wet", "for-art", "for-oth", "for-wat",
          "gra-for", "gra-gra", "gra-agr", "gra-wet", "gra-art", "gra-oth", "gra-wat",
          "agr-for", "agr-gra", "agr-agr", "agr-wet", "agr-art", "agr-oth", "agr-wat",
          "wet-for", "wet-gra", "wet-agr", "wet-wet", "wet-art", "wet-oth", "wet-wat",
          "art-for", "art-gra", "art-agr", "art-wet", "art-art", "art-oth", "art-wat",
          "oth-for", "oth-gra", "oth-agr", "oth-wet", "oth-art", "oth-oth", "oth-wat",
          "wat-for", "wat-gra", "wat-agr", "wat-wet", "wat-art", "wat-oth", "wat-wat"]

def get_lc_transitions(out):
    # multiply pixel area by the area which experienced each of the lc 
    # transition classes --> output: area in ha
    lc_transitions = te_land.select("lc_tr").eq([11,12,13,14,15,16,17,21,22,23,24,25,26,26,31,32,33,34,35,36,37,41,42,43,44,45,46,47,51,52,53,54,55,56,57,
                  61,62,63,64,65,66,67,71,72,73,74,75,76,77]).rename(lc_tr_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['lc_transition_hectares'] = get_fc_properties(lc_transitions, normalize=False)
threads.append(GEECall(get_lc_transitions, out))

def get_soc_pch(out):
    # s3_07: percent change in soc stocks between 2001-2015
    soc_pch_img = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_deg").select("soc_pch")

    # compute statistics for region
    soc_pch = soc_pch_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, 
                                       scale=250, maxPixels=MAX_PIXELS, bestEffort=True)
    # Multiple by 100 to convert to a percentage
    out['soc_change_percent'] = soc_pch.getInfo()['soc_pch'] * 100
threads.append(GEECall(get_soc_pch, out))

def get_soc_change_tons_co2e(out):
    # s3_08: change in soc stocks in tons of co2 eq between 2001-2015
    soc_an_img = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_soc_globe_2001-2015_annual_soc")

    # compute change in SOC between 2001 and 2015 converted to co2 eq
    soc_chg_an = (soc_an_img.select('y2015').subtract(soc_an_img.select('y2001'))).multiply(ee.Image.pixelArea()).divide(10000).multiply(3.67)
    # compute statistics for the region
    soc_chg_tons_co2e = soc_chg_an.reduceRegion(reducer=ee.Reducer.sum(), 
                                                geometry=aoi, scale=250, 
                                                maxPixels=MAX_PIXELS, bestEffort=True)
    out['soc_change_tons_co2e'] = soc_chg_tons_co2e.getInfo()['y2015']
threads.append(GEECall(get_soc_change_tons_co2e, out))

###########################################################
# Ecosystem services

def get_ecosystem_service_dominant(out):
    # dominant ecosystem service
    dom_service = ee.Image("users/geflanddegradation/toolbox_datasets/ecoserv_greatesttotalrealisedservice")

    # define the names of the fields
    es_fields = ["none","carbon", "nature-basedtourism", "culture-basedtourism", "water", "hazardmitigation", "commercialtimber", "domestictimber", "commercialfisheries",
                  "artisanalfisheries", "fuelwood", "grazing", "non-woodforestproducts", "wildlifedis-services", "wildlifeservices", "environmentalquality"]

    # multiply pixel area by the area which experienced each of the three transitions --> output: area in ha
    dom_serv_area = dom_service.eq([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]).rename(es_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())

    # table with areas of each of the dominant ecosystem services in the area
    out['ecosystem_service_dominant'] = get_fc_properties(dom_serv_area, normalize=True, scaling=100)
threads.append(GEECall(get_ecosystem_service_dominant, out))

def get_ecosystem_service_value(out):
    # Relative realised service index (0-1)
    eco_serv_index = ee.Image("users/geflanddegradation/toolbox_datasets/ecoserv_total_real_services")

    # compute statistics for the region
    eco_s_index_mean = eco_serv_index.reduceRegion(reducer=ee.Reducer.mean(),
                                                       geometry=aoi, scale=10000, 
                                                       maxPixels=MAX_PIXELS, bestEffort=True)
    # mean ecosystem service relative index for the region
    out['ecosystem_service_value'] = eco_s_index_mean.getInfo()['b1']
threads.append(GEECall(get_ecosystem_service_value, out))

for t in threads:
    t.join()
sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=4, sort_keys=True))
