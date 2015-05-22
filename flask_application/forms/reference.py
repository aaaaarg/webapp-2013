from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import TextAreaField, HiddenField, Field
from wtforms.widgets import TextInput
from wtforms.validators import Required, URL

from ..models import Annotation, Reference

class TagListField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return u', '.join(self.data)
        else:
            return u''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',')]
        else:
            self.data = []


class BaseReferenceForm(Form):
    tags_proxy = TagListField(u'Tags')


ReferenceForm = model_form(Reference, base_class=BaseReferenceForm, field_args = {
    'pos' : {
      'validators' : [Required()],
      'label' : 'Position (vertical)'
    },
    'pos_x' : {
      'label' : 'Position (horizontal)'
    },
    'pos_end' : {
      'label' : 'Position end (vertical)'
    },
    'pos_end_x' : {
      'label' : 'Position end (horizontal))'
    },
    'note' : {
      'label' : 'A short note'
    },
    'ref_url' : {
    	'validators' : [URL(), Required()],
      'label' : 'Reference URL'
    },
})
