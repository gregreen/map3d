
import numpy as np
import healpy as hp

import json


def get_los(map_query, l, b):
    mu = np.linspace(4., 19., 31).tolist()
    
    los_data = map_query(l, b)
    
    if los_data == None:
        best = np.zeros(len(mu)).tolist()
        samples = [best]
        n_stars = 0
        converged = 0
        
        return mu, best, samples, n_stars, converged
    
    best = los_data['best'].tolist()
    samples = los_data['samples'].tolist()
    n_stars = los_data['n_stars'].tolist()
    converged = int(np.all(los_data['GR'] < 1.2))
    
    #mu_0 = np.random.normal(loc=10., scale=3.)
    #sigma = 0.5 + 4.5 * np.random.random()
    #dE = np.random.random(mu.shape) * np.exp(-0.5 * ((mu-mu_0)/sigma)**2.)
    #E = np.cumsum(dE)
    
    return mu, best, samples, n_stars, converged


def get_encoded_los(map_query, l, b):
    return [json.dumps(d) for d in get_los(map_query, l, b)]
