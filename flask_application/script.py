import datetime, sys, traceback
from pymongo import MongoClient

from mongoengine.errors import ValidationError

from flask.ext.script import Command, Option
from flask.ext.security.utils import encrypt_password
from flask_application import user_datastore, app
from flask_application.populate import populate_data
from flask_application.models import db, solr, User, Role, Thing, Maker, Upload, Reference, Collection, SuperCollection, CollectedThing, Thread, Comment, Queue, TextUpload


class ResetDB(Command):
  """Drops all tables and recreates them"""
  def run(self, **kwargs):
    for m in [User, Role, Collection, Thing, Maker, Thread, Queue]:
      m.drop_collection()

class PopulateDB(Command):
  """Fills in predefined data into DB"""
  def run(self, **kwargs):
    populate_data()

class SolrReindex(Command):
	"""Drops one or more content types from solr"""
	option_list = (
		Option('--do', '-d', dest='todo'),
	)
	def run(self, todo):
		if todo:
			if todo=='things' or todo=='all':
				print 'dropping things index'
				solr.delete(queries=solr.Q(content_type="thing"))
				solr.commit()
				print 'reindexing things'
			if todo=='collections' or todo=='all':
				print 'dropping collections index'
				solr.delete(queries=solr.Q(content_type="collection"))
				solr.commit()
				print 'reindexing collections'
			if todo=='makers' or todo=='all':
				print 'dropping makers index'
				solr.delete(queries=solr.Q(content_type="maker"))
				solr.commit()
				print 'reindexing makers'
				for m in Maker.objects().all():
					m.add_to_solr()
			if todo=='discussions' or todo=='all':
				print 'dropping discussions index'
				solr.delete(queries=solr.Q(content_type="thread"))
				solr.commit()
				print 'reindexing discussions'


class FixMD5s(Command):
	""" Clears out duplicate uploads (based on md5) """
	def run(self, **kwargs):
		def check_upload(upload):
			t = Thing.objects.filter(files=upload).first()
			if not t: # the upload isn't being used, so let's delete it
				print "deleting", upload.structured_file_name
				upload.delete()
		def check_md5(md5):
			uploads = Upload.objects.filter(md5=md5)
			if len(uploads)>1:
				first = None
				for u in uploads:
					if not first:
						first = u
					else:
						print "deleting", u.structured_file_name
						Reference.objects(upload=u).update(set__upload=first)
						Reference.objects(ref_upload=u).update(set__ref_upload=first)
						u.delete()

		# purge uploads that are not in use
		uploads = Upload.objects.all()
		print "CHECKING EMPTIES"
		for u in uploads:
			check_upload(u)
		md5s = Upload.objects.distinct('md5')
		print "CHECKING MD5"
		for md5 in md5s:
			check_md5(md5)
		