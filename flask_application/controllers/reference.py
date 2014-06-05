#!/usr/bin/env python

import datetime, os
from math import floor
from PIL import Image

from flask import Blueprint, request, redirect, url_for, render_template, send_file
from flask_application import app
from flask_images import resized_img_src

from ..models import *

reference = Blueprint('reference', __name__)

@reference.route('/ref/<string:md5>')
def figleaf(md5):
	"""
	The filename here is the structured filename
	"""
	u = Upload.objects.get_or_404(md5=md5)
	things = Thing.objects.filter(files=u)
	preview = u.preview()
	preview_url = url_for('upload.serve_upload', filename=preview) if preview else False

	if not preview_url:
		abort(404)

	return render_template('upload/figleaf.html',
		preview = preview_url,
		things = things
		)

@reference.route('/clip/<string:md5>/<string:boundaries>.jpg')
def citation(md5, boundaries):
	'''
	Serves an image excerpt pages, with clipping boundaries defined
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
		# Loads a clip of a page with fr (top) and to (bottom)
		def load_clip(d, fr, to):
			page_path = os.path.join(d, lg_filename_format%int(fr))
			if os.path.exists(page_path):
				im = Image.open(page_path)
				w, h = im.size
				if int(to)>int(fr):
					to = int(fr) + 1
				return im.crop((0, int(h*(fr-int(fr))), w, int(h*(to-int(fr)))))
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