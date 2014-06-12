from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import TextAreaField, HiddenField
from wtforms.validators import Required, URL

from ..models import Annotation, Reference


ReferenceForm = model_form(Reference, base_class=Form, field_args = {
    'pos' : {
      'validators' : [Required()],
      'label' : 'Position'
    },
    'note' : {
      'label' : 'A short note'
    },
    'ref_url' : {
    	'validators' : [URL()],
      'label' : 'Reference URL'
    },
})