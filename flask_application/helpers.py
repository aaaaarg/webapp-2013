import os
import dateutil.parser
import datetime
import math
import json
import time
import unicodedata
from flask import abort, Blueprint, url_for
from functools import wraps

from lxml import etree
import xmltodict

from zipfile import ZipFile
import urllib2
from io import BytesIO

import isbnlib

# using open library api
from flask_application import app
from olclient.openlibrary import OpenLibrary
from collections import namedtuple
Credentials = namedtuple('Credentials', ['username', 'password'])
open_library = OpenLibrary(credentials = Credentials(app.config['OL_USERNAME'], app.config['OL_PASSWORD']))



# opf writing
DC = "http://purl.org/dc/elements/1.1/"
DCNS = "{http://purl.org/dc/elements/1.1/}"
OPF = 'http://www.idpf.org/2007/opf'

# Caching


def cached(app, timeout=5 * 60, key='view/%s'):
    '''http://flask.pocoo.org/docs/patterns/viewdecorators/#caching-decorator'''
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = key % request.path
            rv = app.cache.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            app.cache.set(cache_key, rv, timeout=timeout)
            return rv
        return decorated_function
    return decorator

# Custom Template Filters


def datetimeformat(value):
    delta = datetime.datetime.now() - value
    if delta.days == 0:
        formatting = 'today'
    elif delta.days < 10:
        formatting = '{0} days ago'.format(delta.days)
    elif delta.days < 28:
        formatting = '{0} weeks ago'.format(int(math.ceil(delta.days / 7.0)))
    elif value.year == datetime.datetime.now().year:
        formatting = '%d %b'
    else:
        formatting = '%d %b %Y'
    return value.strftime(formatting)

keyspace = "wf59eorpma2vnxb07kiqt83_u6lgzs41-ycdjh"


def int_str(val):
    """ Turn a positive integer into a string. """
    assert val >= 0
    out = ""
    while val > 0:
        val, digit = divmod(val, len(keyspace))
        out += keyspace[digit]
    return out[::-1]


def str_int(val):
    """ Turn a string into a positive integer. """
    out = 0
    for c in val:
        out = out * len(keyspace) + keyspace.index(c)
    return out


def chaffify(val, chaff_val=25978):
    """ Add chaff to the given positive integer. """
    return val * chaff_val


def dechaffify(chaffy_val, chaff_val=25978):
    """ Dechaffs the given chaffed value. If the value does not seem to be correctly chaffed, raises a ValueError. """
    val, chaff = divmod(chaffy_val, chaff_val)
    if chaff != 0:
        raise ValueError("Invalid chaff in value")
    return val


def encode_id(val):
    """
     Encodes ID into semi random set of strings
    """
    return int_str(chaffify(val))


def decode_id(val):
    return dechaffify(str_int(val))


def escapejs(val):
    return json.dumps(str(val))


def nl2br(val):
    return val.replace('\n', '<br>\n')


def split_path(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:  # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts


def parse_pos(s):
    '''
    Position should be in one of the following formats:
    a) 123.1 => vertical only
    b) 123.1-124.2 => vertical range
    c) 11.1,123.1 => a point
    d) 11.1,123.1-200.9,124.2 => range between 2 points
    '''
    def parse_point(x):
        if ',' in x:
            return map(float, x.split(','))
        else:
            return [None, float(x)]

    try:
        if '-' in s:
            a, b = map(parse_point, s.split('-'))
        else:
            a, b = parse_point(s), [None, None]
    except:
        return None, None, None, None

    if b[1] is not None and a[1] > b[1]:
        return b[0], b[1], a[0], a[1]
    elif a[1] == b[1] and a[0] is not None and b[0] is not None and a[0] > b[0]:
        return b[0], b[1], a[0], a[1]
    else:
        return a[0], a[1], b[0], b[1]


def merge_dicts(*dict_args):
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def write_opf(meta_info, primary_id=None, path=None):
    if primary_id is None:
        for k, v, a in meta_info:
            if k == DCNS + 'identifier':
                primary_id = a.setdefault('id', 'primary_id')
                break

    root = etree.Element('package', {
        'xmlns': OPF,
        'unique-identifier': primary_id,
        'version': '2.0'
    }, nsmap={'dc': DC, 'opf': OPF})

    metadata = etree.SubElement(root, 'metadata')
    for key, text, attrs in meta_info:
        el = etree.SubElement(metadata, key, attrs)
        try:
            el.text = text
        except:
            pass

    guide = etree.SubElement(root, 'guide')
    el = etree.SubElement(guide, 'reference', {
                          'href': 'cover.jpg', 'type': 'cover', 'title': 'Cover'})

    tree_str = etree.tostring(root, pretty_print=True, encoding='utf-8')
    if path:
        with open(path, 'w') as f:
            f.write(tree_str)
        return path
    else:
        return tree_str


def thing2opf(thing, path=None):
    d = datetime.datetime.now()
    meta = [
        ('{%s}identifier' % DC, 'Unknown', {
         '{%s}scheme' % OPF: 'uuid', 'id': 'uuid_id'}),
        ('{%s}identifier' % DC, '%s.1' %
         str(thing.id), {'{%s}scheme' % OPF: 'ARG'}),
        ('{%s}title' % DC, thing.title, {}),
        ('{%s}date' % DC, d.strftime('%Y-%m-%dT%H:%M:%S+00:00'), {}),
    ]
    try:
        if thing.description:
            meta.append(('{%s}description' % DC, thing.description, {}))
        makers = [(m.maker.display_name, m.maker.sort_by) for m in thing.makers]
        for display, sort_by in makers:
            meta.append(('{%s}creator' % DC, display, {'{%s}file-as' %
                                                       OPF: sort_by, '{%s}role' % OPF: 'aut'}))
    except:
        pass
    return write_opf(meta, None, path)


def opf2dict(opf_str):
    opf_str = opf_str.replace("<?xml version='1.0' encoding='utf-8'?>", "")
    try:
        return xmltodict.parse(opf_str)
    except:
        return {}

""" Given some text (.opf file as xml), this looks for an aaaarg id """


def opf2id(opf_str):
    try:
        d = opf2dict(opf_str)
        ids = d['package']['metadata']['dc:identifier']
        for id in ids:
            if id['@opf:scheme'] == 'ARG':
                return id['#text'].split('.')[0]
    except:
        return None
    return None

""" Given some text (.opf file as xml), this looks for its revision """


def opf_version(opf_str):
    try:
        d = opf2dict(opf_str)
        ids = d['package']['metadata']['dc:identifier']
        for id in ids:
            if id['@opf:scheme'] == 'ARG':
                return int(id['#text'].split('.')[1])
    except:
        return 0
    return 0

""" Given some text (.opf file as xml), this looks for its date """


def opf_date(opf_str):
    d = opf2dict(opf_str)
    try:
        # check for calibre timestamp first
        for m in d['package']['metadata']['meta']:
            if m['@name'] == 'calibre:timestamp':
                ts = time.strptime(m['@content'], '%Y-%m-%dT%H:%M:%S.%f+00:00')
                return datetime.datetime(*ts[:6])
    except:
        pass
    try:
        # this is the arg timestamp given on creation
        ts = time.strptime(d['package']['metadata'][
                           'dc:date'], '%Y-%m-%dT%H:%M:%S+00:00')
        return datetime.datetime(*ts[:6])
    except:
        return None
    return None


"""
Calibre-style paths refer to database models.
Returns a tuple (Maker, Thing, Upload) with as much as it can figure out.
subdir/Author Name/Title of Thing/File name.ext returns (Maker, Thing, Upload)
"""


def path_to_model(path):
    from flask_application import app
    parts = split_path(path)
    if parts[0] == '/':
        parts = parts[1:]
    if parts[0] == app.config['UPLOADS_SUBDIR']:
        parts = parts[1:]
    # @todo:
    return (None, None, None)

"""
Calibre names things in this way: Author Name/Title of Book/Title of Book.xyz
but we might also put metadata.opf or cover.jpg here, so this function just 
returns the full system path ending with "Author Name/Title of Book"
"""


def compute_thing_file_path(thing, filename, makedirs=False):
    from flask_application import app

    def safe_name(str):
        # return "".join([c for c in str if c.isalpha() or c.isdigit() or c=='
        # ']).rstrip()[:64]
        s = "".join([c for c in str if c.isalpha()
                     or c.isdigit() or c == ' ']).rstrip()
        return unicodedata.normalize('NFKD', unicode(s)).encode('ascii', 'ignore')

    author, title = thing.get_maker_and_title()
    # Get the parts of the new path
    directory1 = safe_name(author)
    directory2 = safe_name(title)
    # put together the new path
    p = os.path.join(app.config['UPLOADS_DIR'], app.config[
                     'UPLOADS_SUBDIR'], directory1, directory2)
    if makedirs and not os.path.exists(p):
        os.makedirs(p)
    return os.path.join(p, filename)


""" Given a list of things to put in a folder """


def archive_things(things):
    s = BytesIO()
    with ZipFile(s, "w") as zf:
        for thing in things:
            archive_thing(thing, zf)
    return s.getvalue()


""" Given a thing, create a calibre folder... if a zipfile is provided, simply add to it """


def archive_thing(thing, zip_file=None):
    from flask_application.models import Metadata
    if not zip_file:
        s = BytesIO()
        zf = ZipFile(s, "w")
        cover_file = 'cover.jpg'
        opf_file = 'metadata.opf'
    else:
        zf = zip_file
        cover_file = os.path.join(str(thing.id), 'cover.jpg')
        opf_file = os.path.join(str(thing.id), 'metadata.opf')
    # Put in the content
    try:
        metadata = Metadata.objects.get(thing=thing)
    except:
        metadata = Metadata(thing=thing)
        metadata.reload()
    opf = metadata.opf.encode('utf-8')
    zf.writestr(opf_file, opf)
    # now add the cover, first looking in filesystem and then trying to
    # generate it
    if os.path.exists(compute_thing_file_path(thing, 'cover.jpg')):
        zf.write(compute_thing_file_path(thing, 'cover.jpg'), cover_file)
    else:
        preview = thing.preview(filename="x500-0.jpg")
        if preview:
            try:
                im = urllib2.urlopen(
                    url_for('reference.preview', filename=preview, _external=True), timeout=2)
                #im = urllib2.urlopen('http://ecx.images-amazon.com/images/I/41tFBEmS-pL._SX331_BO1,204,203,200_.jpg')
                cp = compute_thing_file_path(thing, 'cover.jpg', makedirs=True)
                with open(cp, 'wb') as f:
                    f.write(im.read())
                zf.write(cp, cover_file)
            except:
                print "Failed to load image: ", preview
    if not zip_file:
        return s.getvalue()


def queryset_batch(queryset, batch_size=50):
    """
    Generator over a queryset that fetches results in batches, transparently to the caller.
    :param queryset: QuerySet object
    :param batch_size:
    :return:
    """
    batch = -1
    keep_going = True
    while keep_going:
        keep_going = False
        batch += 1
        for t in queryset.skip(batch * batch_size).limit(batch_size):
            yield t
            keep_going = True

def ol_metadata(olid = False, isbn = False):
    # Cleaning empty values
    def clean_empty(d):
        if not isinstance(d, (dict, list)):
            return d
        if isinstance(d, list):
            return [v for v in (clean_empty(v) for v in d) if v]
        return {k: v for k, v in ((k, clean_empty(v)) for k, v in d.items()) if v}
    # There are lots of objects returned, so we need to transform into dicts
    def obj_to_dict(obj, exclusions=[]):
        d = obj.__dict__
        ret = {}
        for key in d:
            if key not in exclusions and d[key]:
                ret[key] = d[key]
        return clean_empty(ret)
    # do the work
    if olid:
        work = open_library.Work.get(olid)
        try:
            editions = work.editions
        except:
            editions = []
        md = obj_to_dict(work, ['_editions', 'created', 'last_modified'])
        md['editions'] = []
        for edition in editions:
            ed = obj_to_dict(edition, ['authors', 'created', 'last_modified'])
            ed['authors'] = []
            for author in edition.authors:
                ad = obj_to_dict(author, ['created', 'last_modified'])
                ed['authors'].append(ad)
            md['editions'].append(ed)
        return md
    elif isbn:
        edition = open_library.Edition.get(isbn=isbn)
        if edition:
            ed = obj_to_dict(edition, ['authors', 'created', 'last_modified'])
            ed['authors'] = []
            for author in edition.authors:
                ad = obj_to_dict(author, ['created', 'last_modified'])
                ed['authors'].append(ad)
            return ed
    # catch all
    return {}


def get_metadata_from_identifiers(ids):
    '''
    Identifiers will be something like: "olid:123456;isbn:1234567890,4321432143"
    '''
    if 'olid' in ids and len(ids['olid']):
        data = ol_metadata(ids['olid'][0])
        if data:
            return data
    if 'isbn' in ids:
        stop_looking = False
        for isbn in ids['isbn']:
            if isbn:
                try:
                    #data = isbnlib.meta(isbn)
                    data = ol_metadata(isbn=isbn)
                    if data:
                        return data
                except:
                    pass
    return {}