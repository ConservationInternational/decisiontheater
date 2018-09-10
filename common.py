# Function to pull areas that are saved as properties within a feature class,
# convert them to percentages of the total area, and return as a dictionary. Sums
# all features together. Scaling converts to percentages if set to 100 and
# scaling is True
def fc_areas_to_pct_dict(fc, normalize=True, scaling=100):
    # Note that there may be multiple features
    ret = {}
    for p in [feature['properties'] for feature in fc.getInfo()['features']]:
        areas = {}
        # If there is more than one feature, need to update ret with these values
        for key, value in p.iteritems():
            if key in ret:
                ret[key] += value
            else:
                ret[key] = value
    if normalize:
        denominator = sum(ret.values())
        ret = {key: (value/denominator)*scaling for key, value in ret.iteritems()}
    return ret
