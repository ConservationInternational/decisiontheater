import re

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
        areas = {}
        # If there is more than one feature, need to update ret with these values
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
        ret = {key: value / denominator for key, value in ret.iteritems()}
    if scaling:
        ret = {key: value * scaling for key, value in ret.iteritems()}
    return ret

def get_coords(geojson):
    """."""
    if geojson.get('features') is not None:
        return geojson.get('features')[0].get('geometry').get('coordinates')
    elif geojson.get('geometry') is not None:
        return geojson.get('geometry').get('coordinates')
    else:
        return geojson.get('coordinates')
