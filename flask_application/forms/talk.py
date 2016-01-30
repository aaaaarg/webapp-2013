from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import TextAreaField, HiddenField
from wtforms.validators import Required

from ..models import Thread, Comment


class BaseThreadForm(Form):
    referenced_type = HiddenField(u'Referenced Document Type', default=None)
    referenced_id = HiddenField(u'Referenced Document Id', default=None)
    text = TextAreaField(u'Write something')


ThreadForm = model_form(Thread, base_class=BaseThreadForm, field_args={
    'title': {
        'validators': [Required()]
    }
})


CommentForm = model_form(Comment, base_class=Form, field_args={
    'text': {
        'validators': [Required()]
    }
})
