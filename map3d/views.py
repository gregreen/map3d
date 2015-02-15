from map3d import app

from flask import render_template, redirect, request, jsonify
import numpy as np
import json
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

@app.route('/expo')
def expo():
    return render_template('expo.html')

@app.route('/usage')
def usage():
    return render_template('usage.html', snippets=snippets)

@app.route('/query')
def query():
    return render_template('query.html')

@app.route('/gal-lb-query', methods=['POST'])
@ratelimit(limit=30, per=60, send_x_headers=False)
def gal_lb_query():
    coords, valid, msg = loscurves.get_coords(request.json, 0)
    
    if not valid:
        return msg, 400
    
    ip = request.remote_addr
    
    dists = [300., 1000., 5000.]
    radius = 7.5
    
    t_start = time.time()
    
    img = postage_stamp.postage_stamps(coords['l'], coords['b'], dists=dists)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    t_ps = time.time()
    
    los_info, table_data = loscurves.get_los(coords)
    
    t_los = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (coords['l'], coords['b'], str(ip))
    txt_request += '(t: %.2fs, ps: %.2fs, los: %.4fs)' % (t_los-t_start, t_ps-t_start, t_los-t_ps)
    
    logger.write(txt_request)
    
    success = int(int(los_info['n_stars']) != 0)
    
    label = ['%d pc' % d for d in dists]
    
    los_info.update(**coords)
    
    for key in los_info.keys():
        los_info[key] = json.dumps(los_info[key])
    
    #for key in los_info.keys():
    #    print key, type(los_info[key])
    #    print los_info[key]
    #    print ''
    
    return jsonify(success=success,
                   radius=radius,
                   label1=label[0], image1=img[0],
                   label2=label[1], image2=img[1],
                   label3=label[2], image3=img[2],
                   table_data=table_data,
                   **los_info)


@app.route('/gal-lb-query-light', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
def gal_lb_query_light():
    # Validate input
    coords, valid, msg = loscurves.get_coords(request.json, max_request_size)
    
    if not valid:
        return msg, 400
    
    # Retrieve the data
    t_start = time.time()
    
    los_info, table_data = loscurves.get_los(coords)
    
    success = None
    if array_like(los_info['n_stars']):
        success = (np.array(los_info['n_stars']) != 0).astype('u1').tolist()
    else:
        success = int(los_info['n_stars'] != 0)
    
    if array_like(coords['l']):
        coords['l'] = coords['l'].tolist()
        coords['b'] = coords['b'].tolist()
        coords['ra'] = coords['ra'].tolist()
        coords['dec'] = coords['dec'].tolist()
    
    t_end = time.time()
    
    # Write to log
    ip = request.remote_addr
    txt_request = None
    if array_like(coords['l']):
        txt_request = '%d coordinates ' % (len(coords['l']))
        txt_request += 'requested by %s ' % (str(ip))
        txt_request += '(t: %.2fs, t/request: %.2gs)' % (t_end-t_start, (t_end-t_start)/len(coords['l']))
    else:
        txt_request = 'l,b = (%.2f, %.2f) ' % (coords['l'], coords['b'])
        txt_request += 'requested by %s ' % (str(ip))
        txt_request += '(t: %.2fs)' % (t_end-t_start)
    
    logger.write(txt_request)
    
    # Return JSON
    los_info.update(**coords)
    
    return jsonify(success=success, **los_info)
