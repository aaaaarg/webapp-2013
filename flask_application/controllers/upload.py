import os

from flask import Blueprint, render_template, flash, request, redirect, url_for, abort, jsonify, send_file
from flask.ext.security import (login_required, roles_required, roles_accepted)

from flask_application import app, tweeter, do_tweets
from flask_application.models import *

#from ..permissions.thing import can_edit_thing

upload = Blueprint('upload', __name__, url_prefix='/upload')


@upload.route('/', methods=['GET', 'POST'])
@upload.route('/thing/<thing_id>', methods=['GET', 'POST'])
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
            u = um.set_uploaded_file(
                file, short_description=request.form.get("short_description")[:255])
            if thing:
                thing.add_file(u)
            uploaded_files.append({
                'url': url_for('upload.serve_upload', filename=u.structured_file_name),
                'structured_file_name': u.structured_file_name,
                'short_description': u.short_description,
                'file_size': u.file_size,
                'mimetype': u.mimetype
            })
        # try to tweet the short description
        if tweeter and do_tweets and thing:
            try:
                text_part = "%s - %s" % (thing.short_description, thing.title)
                tweeter.PostUpdate("%s %s" % (text_part[:89].encode(
                    'utf8'), url_for('thing.detail', id=thing_id, _external=True)))
            except:
                pass
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
    try_path = u.full_path().encode(
        'utf-8') if u else os.path.join(app.config['UPLOADS_DIR'], filename.encode('utf-8'))

    if try_path and os.path.exists(try_path):
        # There is a problem with epub
        if u and u.mimetype == 'application/epub+zip':
            return send_file(try_path, 'application/epub')
        # The normal way
        return send_file(try_path)

    abort(404)


@upload.route('/preview/<path:filename>')
def serve_preview(filename):
    """
    The filename here is the structured filename
    """
    return serve_upload(filename)


@upload.route('/check/<md5>')
@login_required
def check_md5(md5):
    u = Upload.objects(md5=md5).first()
    if u:
        thing = Thing.objects(files=u).first()
    if thing:
        return jsonify({
            'message':'Success', 
            'data':str(thing.id)
        })
    return jsonify({
        'message':'None', 
    })


@upload.route('/recover/<path:filename>')
@roles_accepted('admin', 'editor')
def recover_broken_file(filename):
    """
    The filename here is the structured filename
    """
    u = Upload.objects(structured_file_name=filename).first()
    if u:
        thing = Thing.objects(files=u).first()
        result = u.recover_broken_file(thing.get_maker_and_title())
    return jsonify({'status': result})
