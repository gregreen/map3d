from map3d import app

from flask import render_template, redirect, request, jsonify
import numpy as np
import time
import os

script_dir = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_dir, '..', 'log', 'argonaut_requests.log')

from rate_limit import ratelimit

from redis_logger import Logger
logger = Logger('argonaut_request_log', log_path)

import postage_stamp
import loscurves
import snippets

from utils import array_like

max_request_size = 1000


@app.route('/')
def cover():
    return render_template('cover.html')

@app.route('/usage')
def usage():
    return render_template('usage.html', snippets=snippets)

@app.route('/query')
def query():
    return render_template('query.html')

@app.route('/gal-lb-query', methods=['POST'])
@ratelimit(limit=30, per=60, send_x_headers=False)
def gal_lb_query():
    l, b = None, None
    
    try:
        l = float(request.json['l'])
        b = float(request.json['b'])
    except:
        return 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')', 400
    
    ip = request.remote_addr
    
    if (b > 90.) or (b < -90.):
        return 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')', 400
    
    dists = [300., 1000., 5000.]
    radius = 7.5
    
    t_start = time.time()
    
    img = postage_stamp.postage_stamps(l, b, dists=dists)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    t_ps = time.time()
    
    mu, best, samples, n_stars, converged, table_data = loscurves.get_encoded_los(l, b)
    
    t_los = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (l, b, str(ip))
    txt_request += '(t: %.2fs, ps: %.2fs, los: %.4fs)' % (t_los-t_start, t_ps-t_start, t_los-t_ps)
    
    logger.write(txt_request)
    
    success = int(int(n_stars) != 0)
    
    label = ['%d pc' % d for d in dists]
    
    return jsonify(success=success,
                   l=l, b=b,
                   radius=radius,
                   label1=label[0], image1=img[0],
                   label2=label[1], image2=img[1],
                   label3=label[2], image3=img[2],
                   mu=mu, best=best, samples=samples,
                   n_stars=n_stars, converged=converged,
                   table_data=table_data)


@app.route('/gal-lb-query-light', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
def gal_lb_query_light():
    # Validate input
    l = request.json['l']
    b = request.json['b']
    
    if array_like(l) != array_like(b):
        return 'l and b must have the same number of entries.', 400
    
    try:
        if array_like(l):
            if len(l) > max_request_size:
                return 'Requests limited to %d coordinates at a time.' % max_request_size, 400
            
            l = np.array(l).astype('f4')
            b = np.array(b).astype('f4')
        else:
            l = float(l)
            b = float(b)
    except:
        return 'Non-numeric coordinates detected.', 400
    
    if np.any((b > 90.) | (b < -90.)):
        return 'Latitude greater than 90 degrees (or less than -90 degrees) detected.', 400
    
    # Retrieve the data
    t_start = time.time()
    
    mu, best, samples, n_stars, converged, table_data = loscurves.get_los(l, b)
    
    success = None
    if array_like(n_stars):
        success = (np.array(n_stars) != 0).astype('u1').tolist()
    else:
        success = int(n_stars != 0)
    
    if array_like(l):
        l = l.tolist()
        b = b.tolist()
    
    t_end = time.time()
    
    # Write to log
    ip = request.remote_addr
    txt_request = None
    if array_like(l):
        txt_request = '%d coordinates ' % (len(l))
        txt_request += 'requested by %s ' % (str(ip))
        txt_request += '(t: %.2fs, t/request: %.2gs)' % (t_end-t_start, (t_end-t_start)/len(l))
    else:
        txt_request = 'l,b = (%.2f, %.2f) ' % (l, b)
        txt_request += 'requested by %s ' % (str(ip))
        txt_request += '(t: %.2fs)' % (t_end-t_start)
    
    logger.write(txt_request)
    
    # Return JSON
    return jsonify(success=success,
                   l=l, b=b, distmod=mu,
                   best=best, samples=samples,
                   n_stars=n_stars, converged=converged)
