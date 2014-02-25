import os, hashlib, unicodedata, re

from flask_application import app

from werkzeug import secure_filename

from . import db, CreatorMixin


class Upload(CreatorMixin, db.Document):
	"""
	Encapsulates a file that has been uploaded. A base class for various specific types
	"""
	meta = {
		'allow_inheritance': True,
	}
	file_name = db.StringField(max_length=255)
	# this is a filename that is based on other application metadata to standardize filenames for users
	structured_file_name = db.StringField(max_length=255, unique=True)
	# if the file is being saved to an alternative uploads location it can be specified here
	file_dir = db.StringField(max_length=255)
	file_size = db.IntField()
	mimetype = db.StringField(max_length=255)
	mimetype_params = db.DictField()
	short_description =db.StringField(max_length=255)
	# precompute some identifiers
	sha1 = db.StringField(max_length=255)
	md5 = db.StringField(max_length=255)


	def set_file(self, file):
		"""
		Assumes properties described in werkzeug.datastructures.FileStorage
		Attempts to set all fields
		"""
		self.file_name = secure_filename(file.filename)
		self.structured_file_name = self.slugify(self.file_name)
		self.mimetype = file.mimetype
		self.mimetype_params = file.mimetype_params
		p = self.full_path()
		file.save(p)
		self.file_size = os.path.getsize(p)
		self.compute_hashes()

	def set_structured_file_name(self, value, appendage=0):
		from . import Upload
		orig_path, ext = os.path.splitext(self.file_name)
		to_slugify = "%s%s" % (value, ext) if appendage==0 else "%s-%s%s" % (value, appendage, ext)
		slugified = self.slugify(to_slugify)
		if not Upload.objects(structured_file_name=slugified).first():
			self.update(set__structured_file_name=slugified)
		else:
			self.set_structured_file_name(value, appendage+1)

	def full_path(self):
		if self.file_name is None or self.file_name.strip() == '':
			return None
		if self.file_dir is None or self.file_dir.strip() == '':
			return os.path.join(app.config['UPLOADS_DIR'], self.file_name)
		return os.path.join(self.file_dir, self.file_name)


	def compute_hashes(self):
		BLOCKSIZE = 65536
		hashers = [ ('md5', hashlib.md5()), ('sha1', hashlib.sha1()) ]
		for name, hasher in hashers:
			try:
				with open(self.full_path(), 'rb') as afile:
					buf = afile.read(BLOCKSIZE)
					while len(buf) > 0:
						hasher.update(buf)
						buf = afile.read(BLOCKSIZE)
				setattr(self, name, hasher.hexdigest())
			except:
				print 'Failed to compute hashes for %s', self.file_name


	def slugify(self, s):
		value, ext = os.path.splitext(s)
		_slugify_strip_re = re.compile(r'[^\w\s-]')
		_slugify_hyphenate_re = re.compile(r'[-\s]+')
		if not isinstance(value, unicode):
			value = unicode(value)
		value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
		value = unicode(_slugify_strip_re.sub('', value).strip().lower())
		return "%s%s" % (_slugify_hyphenate_re.sub('-', value), ext)



class TextUpload(Upload):
	num_pages = db.IntField()