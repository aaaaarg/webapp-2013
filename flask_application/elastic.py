"""
This is an Elastic Search interface that is geared towards the kinds of 
queries that this application will execute. For example, filtered queries.
"""

from elasticsearch import Elasticsearch

class ES(object):
	
	def __init__(self, app, *args, **kwargs):
		self.index_name = 'aaaarg'
		self.elastic = Elasticsearch(app.config['ES_SERVER_URLS']) 
	
	def build_query_body(self, query=None, filter=None):
		''' Handles simple keyword queries filtered by something '''
		body = { 'query':{ } }
		query_body = None
		filter_body = None
		if query:
			if type(query) is dict:
				query_body = {
					"query_string" : {
						"default_field" : query.keys()[0],
						"query" : query.values()[0]
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


	def search(self, doc_type, query):
		result = self.elastic.search(
			index=self.index_name, 
			doc_type=doc_type, 
			q=query)
		if 'hits' in result and 'hits' in result['hits']:
			return [(hit['_id'], hit['_source']) for hit in result['hits']['hits']]


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
		r = self.elastic.count(**kwargs)
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
		
	def delete(self, obj):
		self.elastic.delete(
			index=self.index_name, 
			doc_type=obj.type, 
			id=str(obj.id))