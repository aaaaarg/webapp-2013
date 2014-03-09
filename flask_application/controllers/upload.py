import os

from flask import Blueprint, render_template, flash, request, redirect, url_for, abort, jsonify, send_file
from flask.ext.security import (login_required, roles_required, roles_accepted)

from flask_application import app
from flask_application.models import *

#from ..permissions.thing import can_edit_thing

upload = Blueprint('upload', __name__, url_prefix='/upload')


ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
"""
def _handleUpload(files):
	if not files:
		return None
	filenames = []
	saved_files_urls = []
	for key, file in files.iteritems():
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			print os.path.join(UPLOAD_FOLDER, filename)
			file.save(os.path.join(UPLOAD_FOLDER, filename))
			saved_files_urls.append(url_for('uploaded_file', filename=filename))
			filenames.append("%s" % (file.filename))
			print saved_files_urls[0]
		return filenames
"""

@upload.route('/', methods= ['GET', 'POST'])
@upload.route('/thing/<thing_id>', methods= ['GET', 'POST'])
@login_required
def handle_upload(thing_id=None):
	"""
	Upload handler
	"""
	try:
		if thing_id is not None:
			thing = Thing.objects.get(id=thing_id)
		files = request.files
		uploaded_files = []
		for key, file in files.iteritems():
			um = UploadManager()
			u = um.set_uploaded_file(file, short_description=request.form.get("short_description")[:255])
			if thing:
				thing.add_file(u)
			uploaded_files.append({
				'url': '#', #url_for('upload.serve_upload', filename=u.structured_file_name), 
				'structured_file_name': u.structured_file_name,
				'short_description': u.short_description,
				'file_size': u.file_size,
				'mimetype': u.mimetype
			})
		return jsonify({'files': uploaded_files})
	except:
		raise
		return jsonify({'status': 'error'})	


@upload.route('/<path:filename>')
@login_required
def serve_upload(filename):
	"""
	The filename here is the structured filename
	"""
	u = Upload.objects(structured_file_name=filename).first()
	try_path = u.full_path() if u else os.path.join(app.config['UPLOADS_DIR'], filename)
	
	if try_path and os.path.exists(try_path):
		return send_file(try_path)

	abort(404)