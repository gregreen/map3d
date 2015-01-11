from map3d import app

from flask import render_template, redirect, request, jsonify

import mapdata
import postage_stamp
import loscurves


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
    
    assert((b <= 90.) and (b >= -90.))
    
    dists = [300., 1000., 5000.]
    
    print 'l,b = (%.2f, %.2f)' % (l, b)
    
    img = postage_stamp.postage_stamps(mapdata.map_pixval,
                                       mapdata.map_nside,
                                       l, b, dists=dists)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    mu, EBV = loscurves.get_encoded_los(mapdata.mapper, l, b)
    
    label = ['%d pc' % d for d in dists]
    
    return jsonify(l=l, b=b,
                   label1=label[0], image1=img[0],
                   label2=label[1], image2=img[1],
                   label3=label[2], image3=img[2],
                   mu=mu, EBV=EBV)
