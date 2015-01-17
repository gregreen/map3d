
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
    
    #print converged
    #converged = np.random.randint(0,2)
    #print converged
    
    return mu, best, samples, n_stars, converged


def get_encoded_los(map_query, l, b):
    return [json.dumps(d) for d in get_los(map_query, l, b)]
