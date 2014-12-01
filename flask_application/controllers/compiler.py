#!/usr/bin/env python

import datetime, os, rfc3987, re
from math import floor

from flask import Blueprint, request, redirect, flash, url_for, render_template, send_file, abort, jsonify
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask_application import app

from ..models import *

compiler = Blueprint('compiler', __name__, url_prefix='/compiler')

@compiler.route('/create', methods= ['GET', 'POST'])
def create():
	user_id = current_user.get_id()
	annotations = Reference.objects.filter(creator=user_id).order_by('-created_at')
	clips = []

	for a in annotations:
		if a.pos_end:
			u = a.upload
			t = a.thing
			y1 = int(a.pos)
			y2 = int(a.pos_end)
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y1, 75)))
			#img = img.replace('/pages/','http://127.0.0.1:8484/')
			page_count = y2 - y1 + 1
			url_part = '%s.pdf/%s-%s/' % (a.upload.md5, y1, y2) if y2>y1 else '%s.pdf/%s/' % (a.upload.md5, y1)
			title = t.title
			clips.append((link,img,title,a.note,page_count, url_part))

	return render_template('compiler/create.html',
		title = "compiler",
		clips = clips
	)