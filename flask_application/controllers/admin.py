from flask import Blueprint, render_template, flash, request, redirect, url_for, abort
from flask.ext.security import (
    login_required, roles_required, roles_accepted, current_user)
from flask.ext import admin
from flask.ext.admin.contrib.fileadmin import FileAdmin
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
    form_excluded_columns = ('invited', 'invited_by')

    def is_accessible(self):
        return current_user.has_role('admin')


class MakerView(ModelView):
    column_filters = ['display_name']
    column_searchable_list = ('display_name',)
    column_list = ('display_name', 'disambiguation', 'sort_by')
    form_excluded_columns = ('creator', 'followers')

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')


class ThingView(ModelView):
    column_filters = ['title']
    column_searchable_list = ('title', 'makers_sorted')
    column_list = ('title', 'makers_sorted')
    form_excluded_columns = ('creator', 'followers', 'makers', 'files')

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')


class CollectionView(ModelView):
    column_filters = ['title']
    column_searchable_list = ('title',)
    column_list = ('title',)
    form_excluded_columns = ('creator', 'followers', 'editors', 'things')

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')


class UploadView(ModelView):
    column_filters = ['structured_file_name']
    column_searchable_list = ('structured_file_name',)
    column_list = ('id', 'structured_file_name')
    form_excluded_columns = ('creator', 'sha1', 'md5')

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')


class ThreadView(ModelView):
    column_filters = ['title', 'last_comment', 'priority']
    column_searchable_list = ('title', 'last_comment_text',)
    column_list = ('title', 'last_comment_text', 'last_comment', 'priority')
    form_excluded_columns = ('creator', 'last_comment_by',
                             'followers', 'comments', 'origin')

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')


class FileView(FileAdmin):

    def is_accessible(self):
        return current_user.has_role('editor') or current_user.has_role('admin')

admin = admin.Admin(app, 'Admin')
admin.add_view(RoleView(Role, endpoint='roleadmin'))
admin.add_view(UserView(User, endpoint='useradmin'))
admin.add_view(MakerView(Maker, endpoint='makeradmin'))
admin.add_view(ThingView(Thing, endpoint='thingadmin'))
admin.add_view(CollectionView(Collection, endpoint='collectionadmin'))
admin.add_view(ThreadView(Thread, endpoint='threadadmin'))
admin.add_view(UploadView(Upload, endpoint='uploadadmin'))
admin.add_view(FileView(assets_upload_dir, '/upload/', name='Files'))
