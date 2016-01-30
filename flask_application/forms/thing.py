from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import TextField, BooleanField, HiddenField
from wtforms.validators import Required

from ..models import Thing


class BaseThingForm(Form):
    # maker field
    makers_raw = TextField(u'Maker(s)', validators=[Required()])
    collection = HiddenField(u'Collection', default=None)

ThingForm = model_form(Thing, base_class=BaseThingForm, field_args={
    'short_description': {
        'validators': [Required()]
    },
    'title': {
        'validators': [Required()]
    },
})
