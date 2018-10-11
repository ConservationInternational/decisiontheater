import re
import threading

import ee

# Function to pull areas that are saved as properties within a feature class,
# convert them to percentages of the total area, and return as a dictionary. Sums
# all features together. Scaling converts to percentages if set to 100 and
# scaling is True
def get_fc_properties(fc, normalize=False, scaling=None, filter_regex=None):
    if filter_regex:
        regex = re.compile(filter_regex)
    # Note that there may be multiple features
    ret = {}
    for p in [feature['properties'] for feature in fc.getInfo()['features']]:
        # If there is more than one feature, need to update ret with these 
        # values
        for key, value in p.iteritems():
            if filter_regex:
                if not regex.match(key):
                    continue
            if key in ret:
                ret[key] += value
            else:
                ret[key] = value
    if normalize:
        denominator = sum(ret.values())
        if denominator == 0:
            # Handle case of all values being zero - in this case can't 
            # normalize by a denomninator of zero, so leave things alone - set 
            # denominator to 1
            denominator = 1
        ret = {key: value / denominator for key, value in ret.iteritems()}
    if scaling:
        ret = {key: value * scaling for key, value in ret.iteritems()}
    return ret


def get_fc_properties_text(fc, filter_regex=None):
    if filter_regex:
        regex = re.compile(filter_regex)
    # Note that there may be multiple features
    ret = []
    for p in [feature['properties'] for feature in fc.getInfo()['features']]:
        this_ret = {}
        for key, value in p.iteritems():
            if filter_regex:
                if not regex.match(key):
                    continue
            this_ret[key] = value
        ret.append(this_ret)
    return ret


def get_coords(geojson):
    """."""
    if geojson.get('features') is not None:
        return geojson.get('features')[0].get('geometry').get('coordinates')
    elif geojson.get('geometry') is not None:
        return geojson.get('geometry').get('coordinates')
    else:
        return geojson.get('coordinates')

class GEEThread(threading.Thread):
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)

def GEECall(target, *args):
    thread = GEEThread(target, *args)
    thread.start()
    return thread


###############################################################################
# Commonly used functions
def get_area(out, aoi):
    # polygon area in hectares
    out['area_hectares'] = aoi.area().divide(10000).getInfo()

def get_pop(out, aoi, MAX_PIXELS=1e9):
    # s2_02: Number of people living inside the polygon in 2015
    pop_cnt = ee.Image("CIESIN/GPWv4/unwpp-adjusted-population-count/2015")
    population = pop_cnt.reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, 
                                      scale=1000, maxPixels=MAX_PIXELS, bestEffort=True)
    out['population'] = population.getInfo()['population-count']

def get_area_sdg(out, aoi):
    # s3_01: SDG 15.3.1 degradation classes 
    te_sdgi = ee.Image("users/geflanddegradation/global_ld_analysis/r20180821_sdg1531_gpg_globe_2001_2015_modis")
    sdg_areas = te_sdgi.eq([-32768,-1,0,1]).rename(["nodata", "degraded", "stable", "improved"]).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())
    out['area_sdg'] = get_fc_properties(sdg_areas, normalize=True, scaling=100)

def get_ecosystem_service_dominant(out, aoi):
    # dominant ecosystem service
    dom_service = ee.Image("users/geflanddegradation/toolbox_datasets/ecoserv_greatesttotalrealisedservice")

    # define the names of the fields
    es_fields = ["none","carbon", "nature-basedtourism", "culture-basedtourism", "water", "hazardmitigation", "commercialtimber", "domestictimber", "commercialfisheries",
                  "artisanalfisheries", "fuelwood", "grazing", "non-woodforestproducts", "wildlifedis-services", "wildlifeservices", "environmentalquality"]

    # multiply pixel area by the area which experienced each of the three transitions --> output: area in ha
    dom_serv_area = dom_service.eq([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]).rename(es_fields).multiply(ee.Image.pixelArea().divide(10000)).reduceRegions(aoi, ee.Reducer.sum())

    # table with areas of each of the dominant ecosystem services in the area
    out['ecosystem_service_dominant'] = get_fc_properties(dom_serv_area, normalize=True, scaling=100)

def get_ecosystem_service_value(out, aoi, MAX_PIXELS=1e9):
    # Relative realised service index (0-1)
    eco_serv_index = ee.Image("users/geflanddegradation/toolbox_datasets/ecoserv_total_real_services")

    # compute statistics for the region
    eco_s_index_mean = eco_serv_index.reduceRegion(reducer=ee.Reducer.mean(),
                                                       geometry=aoi, scale=10000, 
                                                       maxPixels=MAX_PIXELS, bestEffort=True)
    # mean ecosystem service relative index for the region
    out['ecosystem_service_value'] = eco_s_index_mean.getInfo()['b1']
