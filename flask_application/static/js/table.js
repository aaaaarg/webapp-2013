(function($) {
	/* */
	var SCANR_DEFAULTS = {
		n_cols: 5,
		th_w: 5,
		th_h: 8,
		page_w: 600,
		page_h: 1000,
  }
  var SCANR = {}

  /**/
  $.Strip = function(ref, strip_url, page_base_pattern) {
  	this.$el = document.createElement("div");
  	this.$el.id = ref;
  	this.$el.style.position = "relative";
  	this.$el.style.float = "left";
  	this.$el.style.paddingRight = "10px";
    this.$el.style.height = '100%';
    this.$el.style.zIndex = '10';
    // For paging
    this.curr_page = 0;
    this.page_base_pattern = page_base_pattern;
    this.setup_focus();
    this.pages = [];
    this.num_pages = 0;
    // Strip image
  	this.strip_url = strip_url;
  	this.load_strip();
  	// highlights
  	this.highlights = []
  }

  /* Gets rid of everything */
	$.Strip.prototype.remove = function() {
		this.$el.style.display = 'none';
		this.pages = null;
		this.$marker = null;
		this.$focus = null;
		this.$el = null;
	}  

  /* Loads a strip image, drawing it to canvas */
	$.Strip.prototype.load_strip = function() {
		var self = this;
		var $img = document.createElement("img");
		$img.onload = function(){
			w = $img.naturalWidth;
		  h = $img.naturalHeight;
		  self.num_pages = h*SCANR.n_cols/SCANR.th_h;
			self.$el.appendChild($img);
		}
		$img.src = this.strip_url;
	}  

	/* Opens a page of the strip */
	$.Strip.prototype.setup_focus = function() {
		var self = this;
		this.$focus = document.createElement("div");
  	this.$focus.style.position = "relative";
  	this.$focus.style.top = "10";
  	//this.$focus.style.left = -1*(SCANR.n_cols*SCANR.th_w)/4;
  	this.$focus.style.float = 'right';
  	this.$focus.style.zIndex = '20';
    this.$focus.style.border = '1px solid red';
    this.$focus.style.display = 'none';
    this.$el.style.opacity = 0.8;
    this.$el.appendChild(self.$focus);
	}  

	/* Simply opens the strip */
	$.Strip.prototype.open = function() {
		if (this.pages.length>0) {
			this.$focus.style.display = 'block';
		} else {
			this.goto(0);
		}
	}

	/* Closes the focus for strip */
	$.Strip.prototype.close = function() {
		this.$focus.style.display = 'none';
	}

	/* Is the focus opened? */
	$.Strip.prototype.opened = function() {
		return (this.$focus.style.display=='block');
	}

	/* Denotes that a strip is 'active' */
	$.Strip.prototype.activate = function() {
		this.$el.style.opacity = 1;
		this.$el.style.borderTop = '5px solid yellow';
	}

	/* Denotes that a strip is 'active' */
	$.Strip.prototype.deactivate = function() {
		this.$el.style.opacity = 0.6;
		this.$el.style.borderTop = 'none';
	}

	/* Highlight a set of pages */
	$.Strip.prototype.clear_highlights = function() {	
		for (var i=0; i<this.highlights.length; i++) {
			this.highlights[i].style.display = 'none';
		}
		this.highlights = [];
	}

	/* Highlight a set of pages */
	$.Strip.prototype.highlight = function(pages) {	
		this.clear_highlights();
		if (pages) {
			for (var i=0; i<pages.length; i++) {
				var page = pages[i];
				var $h = document.createElement("div");
				$h.style.position = 'absolute';
		  	$h.style.zIndex = '19';
		  	$h.style.width = SCANR.th_w;
		    $h.style.height = SCANR.th_h;
		    $h.style.backgroundColor = 'orange';
		    $h.style.opacity = '0.5';
		    $h.style.top = Math.floor(page/SCANR.n_cols)*SCANR.th_h;
			  $h.style.left = (page%SCANR.n_cols)*SCANR.th_w;	
		    this.$el.appendChild($h);
		    this.highlights[i] = $h;
			}
		}
	}

	/* Show a minifocus marker */
	$.Strip.prototype.marker = function(page) {
		if (!this.$marker) {
			this.$marker = document.createElement("div");
			this.$marker.style.position = 'absolute';
	  	this.$marker.style.zIndex = '20';
	  	this.$marker.style.width = SCANR.th_w;
	    this.$marker.style.height = SCANR.th_h;
	    this.$marker.style.backgroundColor = 'red';
	    this.$el.appendChild(this.$marker);
	    //this.$marker.style.display = 'none';
		}
		this.$marker.style.top = Math.floor(page/SCANR.n_cols)*SCANR.th_h;
	  this.$marker.style.left = (page%SCANR.n_cols)*SCANR.th_w;	
	}

	/* Preloads a page */
	$.Strip.prototype.preload = function(page) {	
		var self = this;
		if (this.pages[page]) {
			return;
		}
    var $img = document.createElement("img");
    $img.onload = function(){
			self.$focus.appendChild($img);
			self.pages[page] = $img;
		}
		$img.style.display = 'none';
		$img.src = this.page_base_pattern.replace('%s',page);
	}

	/* Opens a page of the strip */
	$.Strip.prototype.goto = function(page) {
		var self = this;
		if (this.pages[page]) {
			this.pages[this.curr_page].style.display = 'none';
			this.pages[page].style.display = 'block';
			this.curr_page = page;
			this.marker(page);
			return;
		}
    var $img = document.createElement("img");
    $img.onload = function(){
			if (self.curr_page>=0 && self.pages.length>0) {
				self.pages[self.curr_page].style.display = 'none';
			}
			self.curr_page = page;
			self.$focus.appendChild($img);
			self.$focus.style.display = 'block';
			self.pages[page] = $img;
			self.marker(page);
			//self.$focus.display = 'block';
			self.preload(page+1);
			self.preload(page+2);
		}
		$img.src = this.page_base_pattern.replace('%s',page);
	}  

		/* Opens a page of the strip */
	$.Strip.prototype.prev = function() {
		if (this.curr_page>0) {
			this.goto(this.curr_page - 1);
		}
	}  	

	/* Opens a page of the strip */
	$.Strip.prototype.skip = function() {
		if (this.curr_page<this.num_pages-SCANR.n_cols) {
			this.goto(this.curr_page + SCANR.n_cols);
			//this.goto(this.curr_page + 1);
		}
	}  

	/* Opens a page of the strip */
	$.Strip.prototype.next = function() {
		if (this.curr_page<this.num_pages-1) {
			this.goto(this.curr_page + 1);
		}
	}  	

  /**/
	$.Table = function(id, basepath, opts) {
		this.basepath = basepath;
		this.strip_pattern = this.basepath + '%r.pdf/%wx%hx%n.jpg';
		this.page_pattern = this.basepath + '%r.pdf/x%w-%s.jpg';

		SCANR.n_cols = opts.n_cols || SCANR_DEFAULTS.n_cols,
    SCANR.th_w = opts.th_w || SCANR_DEFAULTS.th_w,
    SCANR.th_h = opts.th_h || SCANR_DEFAULTS.th_h,
    SCANR.page_w = opts.page_w || SCANR_DEFAULTS.page_w,
    SCANR.page_h = opts.page_h || SCANR_DEFAULTS.page_h,

    this.strip_pattern = this.strip_pattern.replace('%w',SCANR.th_w);
    this.strip_pattern = this.strip_pattern.replace('%h',SCANR.th_h);
    this.strip_pattern = this.strip_pattern.replace('%n',SCANR.n_cols);
    this.page_pattern = this.page_pattern.replace('%w',SCANR.page_w);

    this.$el = document.getElementById(id);
    this.$el.style.position = "relative";
    this.$el.style.width = '100%';
    this.$el.style.height = '100%';
    this.$el.style.border = '1px solid black';

    // every text is called a strip
    focus_strip = -1;
    this.strips = [];

    // events
    this.$el.onkeypress = this._handle_keypress.bind(this);

	}

	$.Table.prototype.add_strip = function(ref) {
		var cf = this.focus_strip;
		var url = this.strip_pattern.replace('%r',ref);
		var pp = this.page_pattern.replace('%r',ref);
		for (var i=0; i<this.strips.length; i++) {
			if (this.strips[i].$el.id==ref) {
				this.change_focus(cf, i);
				return true;
			}
		}
		var s = new Strip(ref, url, pp);
		this.strips[this.strips.length] = s;
		this.$el.appendChild(s.$el);
		this.focus_strip = this.strips.length-1;
		this.change_focus(cf, this.focus_strip);
	}

	$.Table.prototype.highlight = function(ref, pages) {
		for (var i=0; i<this.strips.length; i++) {
			if (this.strips[i].$el.id==ref) {
				this.strips[i].highlight(pages);
			}
		}
	}

	$.Table.prototype.clear_highlights = function() {
		for (var i=0; i<this.strips.length; i++) {
			this.strips[i].clear_highlights();
		}
	}

	$.Table.prototype.goto = function(ref, page) {
		for (var i=0; i<this.strips.length; i++) {
			if (this.strips[i].$el.id==ref) {
				this.strips[i].goto(page);
			}
		}
	}

	$.Table.prototype.change_focus = function(from, to) {
			if (this.strips.length>0 && from<this.strips.length) {
	    	this.strips[from].deactivate();
    	}
    	this.strips[to].activate();
	}

	$.Table.prototype._handle_keypress = function(ev) {
		ev.preventDefault();
		if (this.strips.length==0) {
  		return false;
  	}
    var self = this;
    var cf = this.focus_strip;
    // check digits first
    if (ev.keyCode >= 48 && ev.keyCode <= 57) {

    }
    // others
    var number_started
    switch (ev.keyCode) {
    	case 37:
    		this.strips[cf].prev();
    	break;
    	case 38: // up
    		this.strips[cf].close();
    	break;
    	case 39:
    		this.strips[cf].next();
    	break;
    	case 40: // dn
    		if (this.strips[cf].opened()) {
    			this.strips[cf].skip();
    		} else {
	    		this.strips[cf].open();
	    	}
    	break;
    	case 9: // tab
	    	if (ev.shiftKey) {
	    		this.focus_strip = cf + 1;
	    	} else {
	    		this.focus_strip = cf - 1;
	    	}
	    	if (this.focus_strip<0) {
	    		this.focus_strip = this.strips.length - 1;
	    	}
	    	if (this.focus_strip>=this.strips.length) {
	    		this.focus_strip = 0;
	    	}
	    	this.change_focus(cf, this.focus_strip);
    	break;
    	case 8: // delete
	    	if (ev.shiftKey) {
		    	this.strips[cf].remove();
		    	this.strips.splice(cf,1);
		    	if (this.focus_strip>=this.strips.length) {
		    		this.focus_strip = this.strips.length - 1;
		    	}
		    }
    	break;
    }
    return false;
  }

})(window);
