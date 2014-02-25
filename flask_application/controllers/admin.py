from flask import Blueprint, render_template, flash, request, redirect, url_for, abort
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask.ext import admin
from flask.ext.admin.contrib import fileadmin
from flask.ext.admin.contrib.mongoengine import ModelView


from flask_application import app, assets_upload_dir
from flask_application.models import *


class RoleView(ModelView):
	column_filters = ['name']

	def is_accessible(self):
		return current_user.has_role('admin')


class UserView(ModelView):
	column_filters = ['username']
	column_searchable_list = ('username', 'email')
	form_ajax_refs = {
		'roles': {
			'fields': ['name']
		}
	}

	def is_accessible(self):
		return current_user.has_role('admin')

class MakerView(ModelView):
	column_filters = ['display_name']
	column_searchable_list = ('display_name',)
	column_list = ('display_name', 'disambiguation', 'sort_by')
	form_excluded_columns = ('creator', 'followers')

	def is_accessible(self):
		return current_user.has_role('editor') or current_user.has_role('admin')


admin = admin.Admin(app, 'Admin')
admin.add_view(RoleView(Role))
admin.add_view(UserView(User))
admin.add_view(MakerView(Maker, endpoint='makeradmin'))
#admin.add_view(fileadmin.FileAdmin(assets_upload_dir, '/uploads/', name='Files'))