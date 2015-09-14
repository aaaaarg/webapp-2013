from elasticsearch import Elasticsearch

class ES(object):
	
	def __init__(self, app, *args, **kwargs):
		self.index = 'aaaarg'
		self.elastic = Elasticsearch(app.config['ES_SERVER_URLS']) 
	
	def search(self, doc_type, query):
		result = self.elastic.search(
			index=self.index, 
			doc_type=doc_type, 
			q=query)
		if 'hits' in result and 'hits' in result['hits']:
			return [(hit['_id'], hit['_source']) for hit in result['hits']['hits']]

	def reindex(self, obj, body):
		''' Indexes an object that has an id and type property '''
		try:
			self.elastic.index(
				index=self.index, 
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
			index=self.index, 
			doc_type=obj.type, 
			id=str(obj.id))