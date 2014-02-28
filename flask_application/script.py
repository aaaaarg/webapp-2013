import datetime, sys, traceback
from pymongo import MongoClient

from mongoengine.errors import ValidationError

from flask.ext.script import Command, Option
from flask.ext.security.utils import encrypt_password
from flask_application import user_datastore, app
from flask_application.populate import populate_data
from flask_application.models import db, solr, User, Role, Thing, Maker, Collection, SuperCollection, CollectedThing, Thread, Comment, Queue, TextUpload


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

class MigrateUsers(Command):
	def run(self, **kwargs):
		for role in ('admin', 'editor', 'contributor'):
			user_datastore.create_role(name=role, description=role)
		user_datastore.commit()

		client = MongoClient()
		db = client.aaaart
		count = 0
		for u in db.people.find(timeout=False):
			if not 'email' in u:
				continue
			try:
				roles = ['admin'] if u['email'].encode('utf-8').strip()=='someone@aaaarg.org' else ['contributor']
				display_name = u['display_name'].encode('utf-8').strip() if 'display_name' in u else 'x'
				password = u['pass'].encode('utf-8').strip() if 'pass' in u else u['email'].encode('utf-8').strip()
				user_datastore.create_user(
					id=u['_id'],
					username=display_name, 
					email=u['email'].encode('utf-8').strip(), 
					#password=encrypt_password(u['email'].encode('utf-8').strip()),
					password=password,
					roles=roles, 
					active=True)
				# create a queue
				q = Queue(title='reading list', description='This reading list was automatically created')
				q.set_creator(User.objects(email=u['email'].encode('utf-8').strip()).first())
				q.save()
				count = count+1
				if count%1000==0:
					print "%s completed " % count 
			except:
				print "Unexpected error:", sys.exc_info()
				try:
					print "ERROR: %s" % u['email'].encode('utf-8').strip()
				except:
					print "ERROR"


class MigrateInvitations(Command):
	def run(self, **kwargs):
		client = MongoClient()
		db = client.aaaart
		count = 0
		for u in db.people.find(timeout=False):
			try:
				inviter = User.objects(id=u['_id']).first()
				if 'invited' in u:
					for uid in u['invited']:
						invitee = User.objects(id=uid).first()
						if invitee:
							inviter.add_invitation(invitee)
							invitee.set_inviter(inviter)
				count = count+1
				if count%1000==0:
					print "%s completed " % count 
			except:
				print "Unexpected error:", sys.exc_info()
				if 'email' in u:
					print "ERROR: %s" % u['email'].encode('utf-8').strip()

class MigrateMakers(Command):
	"""Migrates old makers table into new structure"""
	def run(self, **kwargs):
		client = MongoClient()
		db = client.aaaart
		count = 0
		default_user = User.objects(email='someone@aaaarg.org').first()
		for old_thing in db.images.find(timeout=False):
			if Thing.objects(id=old_thing['_id']).first():
				continue
			if old_thing['owner'] and old_thing['owner'] is not None:
				owner = User.objects(id=old_thing['owner']).first()
			if not owner:
				owner = default_user	
			try:
				if 'metadata' in old_thing:
					description = old_thing['metadata']['description'].encode('utf-8').strip() if 'description' in old_thing['metadata'] else ""
					short_description = old_thing['metadata']['one_liner'].encode('utf-8').strip() if 'short_description' in old_thing['metadata'] else ""
				else:
					description = ''
					short_description = ''
				
				thing = Thing(
					title=old_thing['title'].encode('utf-8').strip(), 
					short_description=short_description,
					description=description,
					id=old_thing['_id'],
					creator=owner,
					created_at=datetime.datetime.fromtimestamp(float(old_thing['created'])))
				makers_string = old_thing['makers_display'].encode('utf-8').strip() if 'makers_display' in old_thing else 'Unknown'
				thing.parse_makers_string(old_thing['makers_display'].encode('utf-8').strip())
				# @todo: files!
				thing.save()
				# add to user queues
				for u in old_thing['saved_by']:
					q = Queue.objects(creator=u).first()
					if q and str(old_thing['owner'])!=str(old_thing['saved_by']):
						q.add_thing(thing)
				print '(%s) saved %s' % (count, old_thing['title'].encode('utf-8').strip())
			except:
				print "Unexpected error:", sys.exc_info()[0]
				print traceback.print_tb(sys.exc_info()[2])
				print "ERROR: %s" % old_thing['title'].encode('utf-8').strip()

class MigrateCollections(Command):
	"""Migrates old collections table into new structure"""
	def run(self, **kwargs):
		client = MongoClient()
		db = client.aaaart
		for old_coll in db.collections.find(timeout=False):
			try:
				collection = User.objects(id=old_coll['_id']).first()
				if not collection:
					collection = SuperCollection(
						id = old_coll['_id'],
						title = old_coll['title'].encode('utf-8').strip(),
						short_description = old_coll['short_description'].encode('utf-8').strip(),
						description=old_coll['metadata']['description'].encode('utf-8').strip(),
						accessibility = old_coll['type'].encode('utf-8').strip(),
						creator = User.objects(id=old_coll['owner']).first(),
						created_at=datetime.datetime.fromtimestamp(float(old_coll['created'])))
					collection.save()
					#print 'saved %s' % old_coll['title'].encode('utf-8').strip()

					if 'sections' in old_coll:
						subcollections = {}
						for section in old_coll['sections']:
							try:
								subcollection = SuperCollection(
									id = section['_id'],
									supercollection = collection,
									title = section['title'].encode('utf-8').strip(),
									description=section['description'].encode('utf-8').strip(),
									accessibility = old_coll['type'].encode('utf-8').strip(),
									creator = User.objects(id=section['owner']).first(),
									created_at=datetime.datetime.fromtimestamp(float(section['created'])))
								subcollection.save()
								subcollections[str(section['_id'])] = subcollection
								collection.add_subcollection(subcollection)
								print '- subcollection: %s' % section['title'].encode('utf-8').strip()
							except:
								print ' - bad subcollection - could not save it'

					for old_thing in old_coll['contents']:
						try:
							t = Thing.objects(id=old_thing['object'].id).first()
							if t:
								ct = CollectedThing(thing=t, note=old_thing['notes'].encode('utf-8').strip())
								ct.set_creator(User.objects(id=old_thing['adder']).first())
								if 'section' in old_thing and old_thing['section'].encode('utf-8').strip() in subcollections:
									subcollections[old_thing['section'].encode('utf-8').strip()].add_thing(ct)
								else:
									collection.add_thing(ct)
						except:
							print ' - - bad thing - could not save it'
							#print '-- added: %s' % t.title
			except Exception,e:
				if 'title' in old_coll:
					print 'failed: %s' % old_coll['title'].encode('utf-8').strip()
				else:
					print 'failed...'
				try:
					print e
				except:
					print 'error and i could not even print into'

class MigrateFollowers(Command):
	def run(self, **kwargs):
		client = MongoClient()
		db = client.aaaart
		count = 0
		for u in db.people.find(timeout=False):
			try:
				user = User.objects(id=u['_id']).first()
				if user:
					if 'following' in u and 'collections' in u['following']:
						for c in u['following']['collections']:
							try:
								collection = Collection.objects(id=c['ref'].id).first()
								if collection:
									collection.add_follower(user)
							except Exception,e:
								print e
								sys.exit()
					count = count+1
					if count%1000==0:
						print "%s completed " % count 
			except:
				print 'bad user'


class MigrateComments(Command):
	def run(self, **kwargs):
		client = MongoClient()
		db = client.aaaart
		default_user = User.objects(email='someone@aaaarg.org').first()
		for t in db.comments.find(timeout=False):
			try:
				if len(t['posts'])>0:
					owner = User.objects(id=t['owner']).first()
					if not owner:
						owner = default_user
					thread = Thread(
						id = t['_id'],
						creator = owner,
						created_at=datetime.datetime.fromtimestamp(float(t['created'])),
						title = t['title'].encode('utf-8').strip()
					)
					r = None
					if t['ref']:
						if t['ref'].collection=='images':
							r = Thing.objects(id=t['ref'].id).first()
						elif t['ref'].collection=='collections':
							r = Collection.objects(id=t['ref'].id).first()
						elif t['ref'].collection=='makers':
							r = Maker.objects(id=t['ref'].id).first()
					if r:
						thread.origin = r
					thread.save()
					for p in t['posts']:
						poster = User.objects(id=p['owner']).first()
						if not poster:
							poster = default_user
						try:
							thread.add_comment(p['text'].encode('utf-8').strip(), poster, datetime.datetime.fromtimestamp(float(p['created'])))
						except Exception,e:
							print 'Could not add a post: %s' % p['text'].encode('utf-8').strip()
			except:
				print 'An error occurred and an entire thread could not be saved: %s' % t


class MigrateFiles(Command):
	"""Migrates old files into new structure"""
	def run(self, **kwargs):
		old_base_dir = '/mess/aaaarg'
		old_base_subdir = 'texts/text'
		client = MongoClient()
		db = client.aaaart
		default_user = User.objects(email='someone@aaaarg.org').first()
		for old_thing in db.images.find(timeout=False):
			thing = Thing.objects(id=old_thing['_id']).first()
			if thing:
				for f in old_thing['files']:
					try:
						owner = User.objects(id=f['uploader']).first()
						if not owner:
							owner = default_user	

						processed_file = db.lookup.find_one({"thing":old_thing['_id'], "file":f['name'].encode('utf-8')})
						# If we've already processed the file, then it's just a matter of 
						if processed_file:
							p = processed_file['path'].encode('utf-8').strip()
							upload = TextUpload(
								short_description= f['comment'].encode('utf-8').strip(),
								sha1= f['sha1'].encode('utf-8').strip(),
								creator = owner,
								created_at = datetime.datetime.fromtimestamp(float(f['upload_date']))
							)
							upload.set_file(p)
							# the name has already been rewritten, so don't do it again
							thing.add_file(upload, False)
						
						else:
							# get local path
							if 'full_path' in f:
								cur_path = f['full_path'].encode('utf-8').strip().replace(old_base_dir, app.config['UPLOADS_DIR'])
							else:
								cur_path = os.path.join(app.config['UPLOADS_DIR'], old_base_subdir, f['name'].encode('utf-8').strip())
							# If we have a valid file, then let's add the upload
							if os.path.exists(cur_path):
								upload = TextUpload(
									short_description= f['comment'].encode('utf-8').strip(),
									sha1= f['sha1'].encode('utf-8').strip(),
									creator = owner,
									created_at = datetime.datetime.fromtimestamp(float(f['upload_date']))
								)
								upload.set_file(cur_path)
								print 'saving',cur_path,'as',upload.file_path
								# allow the name to be rewritten
								thing.add_file(upload)
					except:
						print "Unexpected error:", sys.exc_info()[0]
						print traceback.print_tb(sys.exc_info()[2])
						print f['name'].encode('utf-8').strip()
						print "ERROR: %s" % old_thing['title'].encode('utf-8').strip()
