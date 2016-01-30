from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form

from wtforms import FileField, HiddenField
from wtforms.validators import Required

from ..models import Upload


class BaseUploadForm(Form):
    # maker field
    files = FileField(u'Upload')

UploadForm = model_form(Upload, base_class=BaseUploadForm,
                        only=['short_description'])
