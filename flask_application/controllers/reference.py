#!/usr/bin/env python

import datetime, os, rfc3987
from math import floor
from PIL import Image

from flask import Blueprint, request, redirect, url_for, render_template, send_file, abort
from flask.ext.security import (login_required, roles_required, roles_accepted)
from flask_application import app

from ..models import *

reference = Blueprint('reference', __name__)

@reference.route('/ref/<string:md5>')
def figleaf(md5):
	"""
	The filename here is the structured filename
	"""
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	thing = Thing.objects.filter(files=u).first()
	preview = u.preview()
	if not preview:
		if u.mimetype=="application/pdf":
			u.request_preview()
			return "A preview will be generated within the next 15 minutes"
		else:
			return "Sorry, I only know how to preview pdfs"
	preview_url = url_for('upload.serve_upload', filename=preview) if preview else False

	# load annotations
	annotations = Reference.objects.filter(upload=u)
	# create a list of referenced things
	references = []
	for a in annotations:
		if a.ref_thing and not a.ref_thing in references:
			references.append(a.ref_thing)
	# for back references
	back_annotations = Reference.objects.filter(ref_upload=u)
	back_references = []
	for a in back_annotations:
		if a.thing and not a.thing in back_references:
			back_references.append(a.thing)
	

	if not preview_url:
		abort(404)

	return render_template('upload/figleaf.html',
		preview = preview_url,
		thing = thing,
		annotations = annotations,
		references = references,
		back_annotations = back_annotations,
		back_references = back_references
		)


@reference.route('/ref/<string:md5>/add/<float:pos>')
@login_required
def create_reference(md5, pos):
	"""
	Adds a reference notation to an upload
	"""
	url = request.args.get('url', '')
	if not rfc3987.match(url, rule='URI'):
		return "Sorry, that's not a valid URL:\n" % url
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	# Create the reference
	r = Reference(upload=u, ref_url=url, pos=pos)
	r.save()
	
	return url
	

@reference.route('/clip/<string:md5>/<string:boundaries>.jpg')
def clip(md5, boundaries):
	'''
	Serves an image excerpt pages, with clipping boundaries defined
	(for now, page height is hardcoded as 1000, so hacky bits reflect that)
	'''
	lg_filename_format = '1024x-%s.jpg'
	clip_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['CLIP_CACHE'], md5)
	clip_path = os.path.join(clip_dir, '%s.jpg' % boundaries)
	if os.path.exists(clip_path):
		return send_file(clip_path)
	# Get the boundaries (expects something like 1.11-2.04)
	bounds = boundaries.split('-')
	if len(bounds)==2:
		try:
			(top, bot) = (float(bounds[0]), float(bounds[1]))
		except ValueError:
			abort(404)
	# Now try and load the file
	u = Upload.objects.get_or_404(md5=md5)
	preview_dir = u.preview_dir()
	if preview_dir:
		def compute_y(y, w):
			return int(float(w)*y*10/7)
		# Loads a clip of a page with fr (top) and to (bottom)
		def load_clip(d, fr, to):
			page_path = os.path.join(d, lg_filename_format%int(fr))
			if os.path.exists(page_path):
				im = Image.open(page_path)
				w, h = im.size
				if int(to)>int(fr):
					to = int(fr) + 1
				# hackish computation of image crop based on how JS addressing is done (still buggy at bottom)
				upper_y, lower_y = (compute_y(fr-int(fr), w), math.min(compute_y(to-int(fr), h))
				return im.crop((0, upper_y, w, lower_y, w)))
				#return im.crop((0, int(1000*(fr-int(fr))), w, int(1000*(to-int(fr)))))
			return False

		im = load_clip(preview_dir, top, bot)
		if not im:
			return 'Sorry'
		if int(bot)-int(top)==1:
			im2 = load_clip(preview_dir, int(bot), bot)
			if im2:
				w1, h1 = im.size
				w2, h2 = im2.size
				new_im = Image.new('RGB', (max(w1,w2),h1 + h2))
				new_im.paste(im, (0,0))
				new_im.paste(im2, (0,h1))
				im = new_im
			print 'another'
			# the clip spans 2 pages so we paste them together
		# Save the clip
		if not os.path.exists(clip_dir):
			os.makedirs(clip_dir)
		im.save(clip_path)
		# Serve it
		return send_file(clip_path) 
	return 'Sorry!'


@reference.route('/ref_clips/<string:md5>')
def reference_clips(md5):
	"""
	A page made of clips
	"""
	u = Upload.objects.filter(md5=md5).first()
	thing = Thing.objects.filter(files=u).first()
	if not u:
		abort(404)
	# load annotations
	annotations = Reference.objects.filter(upload=u).order_by('pos')
	clips = []

	for a in annotations:
		if a.ref_upload and a.ref_pos:
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor=a.pos)
			if a.ref_pos_end:
				img = url_for("reference.clip", md5=a.ref_upload.md5, boundaries="%s-%s" % (a.ref_pos, a.ref_pos_end))
				clips.append((link,img))
			else:
				img = url_for("reference.clip", md5=a.ref_upload.md5, boundaries="%s-%s" % (int(a.ref_pos), int(a.ref_pos)+1))
				clips.append((link,img))

	return render_template('upload/clips.html',
		thing = thing,
		clips = clips
	)