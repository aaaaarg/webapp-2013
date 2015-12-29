"""
This is an Elastic Search interface that is geared towards the kinds of 
queries that this application will execute. For example, filtered queries.
"""
import re
from elasticsearch.exceptions import ConnectionTimeout
from elasticsearch import Elasticsearch

class ES(object):
	
	def __init__(self, app, *args, **kwargs):
		self.index_name = 'aaaarg'
		self.elastic = Elasticsearch(app.config['ES_SERVER_URLS']) 
	
	def build_query_body(self, query=None, filter=None, min_size=None):
		''' Handles simple keyword queries filtered by something. 
		query = Lucene query string with no filter or a dict for the query
		filter = dict of fields to filter by.
		Highlight is an optional field name '''
		body = { 'query':{ } }
		query_body = None
		filter_body = None
		highlight_body = None
		if query:
			if type(query) is dict:
				field_str = query.keys()[0]
				query_str = re.escape(query.values()[0])
				if ',' in field_str:
					query_body = {
						"multi_match" : {
							"fields" : field_str.split(','),
							"query" : query_str,
							"type" : "phrase"
						}
					}
				else:
					query_body = {
						"match_phrase" : {
							field_str : query_str
						}
					}
			else:
				query_body = {
					"query_string" : {
						"query" : query
					}
				}
		if filter and type(filter) is dict:
			if len(filter)==1:
				filter_body = { 'term': filter }
			else:
				filter_body = [ {'term' : {f: filter[f]} } for f in filter]
			body['query']['filtered'] = {
				'filter': {
					'bool': {
						'must': filter_body
					}
				}
			}
		if query_body and filter_body:
			body['query']['filtered']['query'] = query_body
		elif query_body and not filter_body:
			body['query'] = query_body

		return body


	def search(self, doc_type, query, filter=None, highlight=None, fields=None, start=None, num=10, min_size=None):
		''' Fields should be a list '''
		kwargs = {
			'index': self.index_name, 
			'doc_type': doc_type, 
			'size': num,
		}
		if query and not filter and not type(query) is dict:
			kwargs['q'] = query
			if start:
				kwargs['body'] = {'from': start }
		else:
			kwargs['body'] = self.build_query_body(query=query, filter=filter, min_size=min_size)
			if highlight:
				kwargs['body']['highlight'] = {
					"fields" : {
						highlight : {}
					}
				}
			if start:
				kwargs['body']['from'] = start
		if fields:
			kwargs['fields'] = fields
		try:
			result = self.elastic.search(**kwargs)
		except ConnectionTimeout:
			return []
		except:
			return []

		if 'hits' in result and 'hits' in result['hits']:
			if fields:
				if highlight:
					return [(hit['_id'], hit['_score'], hit['fields'], hit['highlight'][highlight]) for hit in result['hits']['hits']]
				else:
					return [(hit['_id'], hit['_score'], hit['fields']) for hit in result['hits']['hits']]
			else:
				return [(hit['_id'], hit['_score'], hit['_source']) for hit in result['hits']['hits']]
		else:
			return []

	def grouped_search(self, doc_type, query, group_field, filter=None, highlight=None, num=10, bucket_size=1, start=None, fields=None, min_size=None):
		kwargs = {
			'index': self.index_name, 
			'doc_type': doc_type, 
			'size': num,
		}
		kwargs['body'] = self.build_query_body(query=query, filter=filter, min_size=min_size)
		kwargs['body']['aggs'] = {
			'byField': {
				'terms': {
					'field': group_field,
					'size': num
				},
				"aggs": {
					"topFoundHits": {
						"top_hits": {
							"size": bucket_size
						}
					}
				}
			}
		}
		if fields:
			kwargs['body']['aggs']['byField']['aggs']['topFoundHits']['top_hits']['_source'] = {
				'include': fields
			}
		#if start:
		#		kwargs['body']['aggs']['aggs']['topFoundHits']['from'] = start
		try:
			result = self.elastic.search(**kwargs)
		except ConnectionTimeout:
			return []
		try:
			buckets = result['aggregations']['byField']['buckets']
		except:
			return []
		groups = []
		for bucket in buckets:
			groups.append((
				bucket['key'],
				bucket['doc_count'],
				[ (hit['_id'], hit['_source']) for hit in bucket['topFoundHits']['hits']['hits']]
			))
		print groups
		return groups


	def count(self, doc_type, query=None, filter=None):
		''' Filter is a dict for matching fields before running the query '''
		kwargs = {
			'index': self.index_name, 
			'doc_type': doc_type, 
		}
		if query and not filter and not type(query) is dict:
			kwargs['q'] = query
		else:
			kwargs['body'] = self.build_query_body(query=query, filter=filter)
		try:
			r = self.elastic.count(**kwargs)
		except:
			return 0
		if 'count' in r:
			return int(r['count'])
		else:
			return 0


	def index(self, obj, body):
		''' Indexes an object that has an id and type property '''
		try:
			self.elastic.index(
				index=self.index_name, 
				doc_type=obj.type, 
				id=str(obj.id), 
				body=body)
		except Exception, e:
			print "Elastic Error: ", e
		except:
			print "Unexpected error:", sys.exc_info()[0]
			print traceback.print_tb(sys.exc_info()[2])
			print d
	

	def get(self, doc_type, id):
		result = self.elastic.get(
			index=self.index_name, 
			doc_type=doc_type, 
			id=id
			)
		if '_source' in result:
			return result['_source']
		else:
			return {}

	def delete(self, obj):
		self.elastic.delete(
			index=self.index_name, 
			doc_type=obj.type, 
			id=str(obj.id))
