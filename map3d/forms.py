from flask.ext.wtf import Form
from wtforms import DecimalField
from wtforms.validators import Required, NumberRange

class GalCoordForm(Form):
    gal_l = DecimalField('gal-l', validators=[Required(message=u'Galactic longitude required.')])
    gal_b = DecimalField('gal-b', validators=[Required(message=u'Galactic latitude required.'), 
                                              NumberRange(min=-90., max=90., message=u'Latitude must be between -90 and 90 degrees')])
