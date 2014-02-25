from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import TextField, BooleanField, HiddenField
from wtforms.validators import Required

from ..models import Queue, QueuedThing



QueueForm = model_form(Queue, base_class=Form, field_args = {
    'short_description' : {
        'validators' : [Required()]
    },
    'title' : {
        'validators' : [Required()]
    }
})


QueuedThingForm = model_form(QueuedThing, base_class=Form, field_args = {
    'description' : {
        'label' : 'Notes'
    },
    'subtitle' : {
        'label' : 'Alternate title'
    },
})