from map3d import app

from flask import render_template, redirect, request, jsonify

import mapdata
import postage_stamp
import loscurves

import time


@app.route('/')
def cover():
    return render_template('cover.html')

@app.route('/query')
def query():
    return render_template('query.html')

@app.route('/gal-lb-query', methods=['POST'])
def gal_lb_query():
    l = float(request.json['l'])
    b = float(request.json['b'])
    ip = request.remote_addr
    
    assert((b <= 90.) and (b >= -90.))
    
    dists = [300., 1000., 5000.]
    radius = 7.5
    
    t_start = time.time()
    
    img = postage_stamp.postage_stamps(mapdata.map_pixval,
                                       mapdata.map_nside,
                                       l, b, dists=dists,
                                       radius=radius)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    t_ps = time.time()
    
    mu, best, samples, n_stars, converged, table_data = loscurves.get_encoded_los(mapdata.map_query, l, b)
    
    t_los = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (l, b, str(ip))
    txt_request += '(t: %.2fs, ps: %.2fs, los: %.4fs)' % (t_los-t_start, t_ps-t_start, t_los-t_ps)
    print txt_request
    
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
