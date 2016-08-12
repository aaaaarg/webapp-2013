(function($) {
	/* */
	var SCANR_DEFAULTS = {
		basepath: '',
		n_results: 10,
		th_w: 40,
		th_h: 50,
  }
  var SCANR = {}

  var getJSON = function(url) {
	  return new Promise(function(resolve, reject) {
	    var xhr = new XMLHttpRequest();
	    xhr.open('get', url, true);
	    xhr.responseType = 'json';
	    xhr.onload = function() {
	      var status = xhr.status;
	      if (status == 200) {
	        resolve(xhr.response);
	      } else {
	        reject(status);
	      }
	    };
	    xhr.send();
	  });
	};

	var buildUrl = function(url, parameters){
	  var qs = "";
	  for(var key in parameters) {
	    var value = parameters[key];
	    qs += encodeURIComponent(key) + "=" + encodeURIComponent(value) + "&";
	  }
	  if (qs.length > 0){
	    qs = qs.substring(0, qs.length-1); //chop off last "&"
	    url = url + "?" + qs;
	  }
	  return url;
	}

	/**/
	$.Result = function(ref, title, author) {
		this.ref = ref;
		this.pages = [];
		this.thumb_pattern = SCANR.basepath + 'pages/%r.pdf/x%w-0.jpg';
		this.refs_url = SCANR.basepath + 'ref/%r/all'.replace('%r', ref);
		this.$el = document.createElement("div");

		var $i = document.createElement("img");
		$i.src = this.thumb_pattern.replace('%w',SCANR.th_w).replace('%r', ref);
		$i.style.marginRight = "10px";
		
		var $t = document.createElement("a");
		$t.innerText = title;
		$t.style.marginRight = "10px";
		$t.style.cursor = "pointer";
		
		var $a = document.createElement("span");
		$a.innerText = author;
		
		this.$el.appendChild($i);
		this.$el.appendChild($t);
		this.$el.appendChild($a);

		$t.onclick = this._handle_click.bind(this);
	}

	/**/
	$.Result.prototype.set_pages = function(pages) {
		this.pages = pages;
		var $p = document.createElement("span");
		$p.innerText = " [found inside]";
		$p.style.color = '#CCCCCC';
		this.$el.appendChild($p);
	}

	/**/
	$.Result.prototype._handle_click = function(ev) {
		var e = new CustomEvent('searchresultclicked', { detail: this });
		document.dispatchEvent(e);
	}


	/**/
	$.Searcher = function(search_id, results_id, button_id, opts) {		
		SCANR.basepath = opts.basepath || SCANR_DEFAULTS.basepath,
		SCANR.n_results = opts.n_results || SCANR_DEFAULTS.n_results,
    SCANR.th_w = opts.th_w || SCANR_DEFAULTS.th_w,
    SCANR.th_h = opts.th_h || SCANR_DEFAULTS.th_h;

		this.base_path = SCANR.basepath;
		this.search_url = SCANR.basepath + 'refsearch';

    this.$search = document.getElementById(search_id);
    this.$results = document.getElementById(results_id);
    this.$button = document.getElementById(button_id);

    this.$button.onclick = this._handle_button.bind(this);
    this.$search.onkeyup = this._handle_key_up.bind(this);
    this.$search.onkeydown = this._handle_key_down.bind(this);
	}  

	  /* execute a search */
  $.Searcher.prototype._handle_button = function() {
		this.search();
	}

	  /* checks if enter, then execute a search */
  $.Searcher.prototype._handle_key_up = function(ev) {
  	ev.preventDefault();
  	if (ev.keyCode == 13) {
        this.$button.click();
    }
	}

  /* ignores enter key */
  $.Searcher.prototype._handle_key_down = function(ev) {
  	if (ev.keyCode == 13) {
        return false;
    }
	}

  /* execute a search */
  $.Searcher.prototype.search = function(query) {
  	if (this.$search.value=='') {
  		return false;
  	}
		this.clear_results();
		//this.listener.clear_highlights();
		this.searching("Searching...");
		var self = this;
		var url = buildUrl(this.search_url,{ 'q':this.$search.value });
		getJSON(url).then(function(data) {
	    self.clear_results();
	    var already = [];
	    for (var i=0; i<data.metadata.length; i++) {
	    	var obj = data.metadata[i];
	    	var r = new Result(obj.ref, obj.title, obj.makers);
				self.add_result(r);
				already[obj.ref] = obj.ref;
	    }
	    for (var i=0; i<data.fulltext.length; i++) {
	    	var obj = data.fulltext[i];
	    	if (!already[obj.ref]) {
		    	var r = new Result(obj.ref, obj.title, obj.makers);
					r.set_pages(obj.pages);
					self.add_result(r);
				}
				//self.listener.highlight(obj.ref, obj.pages);
	    }
		}, function(status) { //error detection....
		  self.clear_results();
			self.searching("There was an error :(");
		});
		
	}

  /* clear results */
	$.Searcher.prototype.clear_results = function() {
		while (this.$results.firstChild) {
	    this.$results.removeChild(this.$results.firstChild);
		}
	}

  /* add a "searching" result */
  $.Searcher.prototype.searching = function(txt) {
  	d = document.createElement("li");
		d.className += 'list-group-item';
  	d.innerText = txt;
  	this.$results.appendChild(d);
  }

  /* add a result */
  $.Searcher.prototype.add_result = function(r) {
  	d = document.createElement("li");
		d.className += 'list-group-item';
  	d.appendChild(r.$el);
  	this.$results.appendChild(d);
  }

})(window);
