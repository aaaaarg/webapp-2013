(function($) {

    var SCANR = {n_cols: 20,
                 th_w: 50,
                 th_h: 72,
                 page_w: 700,
                 page_h: 1000,
                 box_h: 300
                }
    $.Figleaf = function($el, basepath) {
        this.basepath = basepath;

        this.$el = $el;
        this.$el.style.position = "relative";
        this.$pdf = $el.querySelector("img");

        // Cover the mosaic with a canvas to visualize position
        this.$canvas = document.createElement("canvas");
        this.$canvas.style.position = "absolute";
        this.$canvas.style.left = 0;
        this.$canvas.style.top = 0;
        this.$canvas.style.zIndex = "5";
        this.$el.appendChild(this.$canvas);

        this.$pdf.onmousedown = this._handle_seek.bind(this);
        this.$canvas.onmousedown = this._handle_seek.bind(this);
        
        // Create a frame for focus
        this.$focus = document.createElement("div");
        this.$focus.style.position = "absolute";
        this.$focus.style.width = SCANR.page_w;
        this.$focus.style.height = SCANR.box_h;
        this.$focus.style.overflowX = "hidden";
        this.$focus.style.overflowY = "auto";
        this.$focus.style.border = "1px solid red";
        this.$focus.style.backgroundColor = "white";
        this.$focus.style.display = "none";
        this.$focus.style.zIndex = "10";
        this.$focus.onscroll = this._handle_scroll.bind(this);
        // capture dragging in the focus frame
        //this.$focus.onmousedown = this._handle_seek.bind(this);
        // capture keystrokes
        window.addEventListener("keydown", this._handle_keypress.bind(this), false);
        // capture double clicks
        this.$focus.addEventListener("dblclick", this._handle_dblclick.bind(this), false);
        //this.$focus.dblclick = this._handle_dblclick.bind(this);

        this.$el.appendChild(this.$focus);

        this.pages_populated = false;
        this._has_focus = false;

        // Make container <divs> for each page that get lazily filled with images
        this.page_containers = [];
    }
    $.Figleaf.prototype._populate_pages = function() {
        // Use width and height of this.$pdf to set height of focus window
        // (assumes thumbnail image is loaded)

        this.width = this.$pdf.width;
        this.height = this.$pdf.height;

        var npages = (this.height / SCANR.th_h) * SCANR.n_cols; // may overshoot
        for(var i=0; i<npages; i++) {
            var $div = document.createElement("div");
            $div.style.width = SCANR.page_w;
            $div.style.height = SCANR.page_h;
            $div.style.overflow = "hidden";
            this.page_containers[i] = $div;
            this.$focus.appendChild($div);
        }
    }
    $.Figleaf.prototype._handle_seek = function(ev) {
        ev.preventDefault();
        var pdf_pos = _el_offset(this.$pdf);
        var rel_x = ev.clientX - pdf_pos.left;
        var rel_y = ev.clientY - pdf_pos.top;

        var row = Math.floor(rel_y / SCANR.th_h);
        var col = Math.floor(rel_x / SCANR.th_w);

        var page = row * SCANR.n_cols + col;
        // Where in the page are we?
        var th_start = ((rel_y / SCANR.th_h) % 1.0);

        // Allow dragging the mouse here
        window.onmousemove = this._handle_seek.bind(this);
        window.onmouseup = function() {
            console.log("up");
            window.onmousemove = undefined;
            window.onmouseup = undefined;
        }

        console.log("page", page, "start", th_start);
        this.seek(page + th_start);
    }
    $.Figleaf.prototype.pageToPos = function(page) {
        return [SCANR.th_w * (Math.floor(page) % SCANR.n_cols),
                SCANR.th_h * Math.floor(Math.floor(page) / SCANR.n_cols) + SCANR.th_h * (page % 1.0)]
    }
    $.Figleaf.prototype.pageToBoxPos = function(page) {
        // Where should the box go?
        var x_percent = (page % SCANR.n_cols) / SCANR.n_cols;
        
        return [(this.width - SCANR.page_w) * x_percent,
                SCANR.th_h * Math.floor(Math.floor(page) / SCANR.n_cols) + SCANR.th_h]
    }
    $.Figleaf.prototype.seek = function(page) {
        if(!this._has_focus) {
            this.$focus.style.display = "block";
            this._has_focus = true;
        }
        if(!this.pages_populated) {
            this._populate_pages();
            this.pages_populated = true;
        }
        this.$focus.scrollTop = page * SCANR.page_h;
    }
    $.Figleaf.prototype.tint = function(page, ratio, color) {
        if (!isNaN(parseInt(page)) && isFinite(page) && !isNaN(parseFloat(ratio)) && isFinite(ratio)) {
            pos = this.pageToPos(page);
            var $div = document.createElement("div");
            $div.className = 'sr';
            $div.style.width = SCANR.th_w;
            $div.style.height = SCANR.th_h;
            $div.style.backgroundColor = color;
            $div.style.position = "absolute";
            $div.style.left = pos[0];
            $div.style.top = pos[1];
            $div.style.opacity = 0.5 * ratio;
            $div.style.zIndex = "6";
            $div.style.pointerEvents = "none";
            this.$el.appendChild($div);
        }
    }
    $.Figleaf.prototype.highlight = function(y1, y2) {
        if (!isNaN(parseFloat(y1)) && isFinite(y1) && !isNaN(parseFloat(y2)) && isFinite(y2)) {
            this.seek(y1 - 0.05);
            var $div = document.createElement("div");
            $div.style.width = SCANR.page_w;
            $div.style.height = SCANR.page_h * (y2-y1);
            $div.style.backgroundColor = "#FFFF00";
            $div.style.position = "absolute";
            $div.style.top = SCANR.page_h * y1;
            $div.style.opacity = 0.3;
            this.$focus.appendChild($div);
        }
    }
    $.Figleaf.prototype.goto_reference = function(str) {
        n = str.split('-');
        if (n.length==1 && !isNaN(parseFloat(n[0])) && isFinite(n[0])) {
            this.seek(n[0]);
        } else if (n.length==2 ) {
            this.highlight(n[0], n[1]);
        }
    }
    $.Figleaf.prototype.edit = function(pos, url) {
        var $div = document.createElement("div");
        $div.innerHTML = "<a target='_new' title='edit' alt='edit' href='"+url+"'><div style='font-size:12px;line-height:10px;background-color:#0000FF;border:1px solid #000;'>&nbsp;</div></a>";
        //$div.style.backgroundColor = "#00FF00";
        //$div.style.border = "1px solid #000";
        $div.style.position = "absolute";
        $div.style.top = SCANR.page_h * pos;
        $div.style.left = SCANR.page_w - 32;
        $div.style.width = 4;
        $div.style.opacity = 0.7;
        this.$focus.appendChild($div);
        //console.log("Reference: " + $div.style.top + "," + $div.style.left);
    }
    $.Figleaf.prototype.reference = function(pos, url, title) {
        var $div = document.createElement("div");
        $div.innerHTML = "<a target='_new' title='"+title+"' alt='"+title+"' style='font-size:12px;padding:0 2 0 2px;line-height:10px;margin-right:2px;background-color:#00FF00;border:1px solid #000;text-decoration:none;color:#000' href='"+url+"'><b>&#10095;</b></a><!--<a target='_new' onclick='moveAnnotation(this)' style='text-decoration:none;cursor:pointer;color:#000;font-size:11px;' href='"+url+"'>&#8597;</a>-->";
        //$div.style.backgroundColor = "#00FF00";
        //$div.style.border = "1px solid #000";
        $div.style.position = "absolute";
        $div.style.top = SCANR.page_h * pos;
        $div.style.left = SCANR.page_w - 28;
        $div.style.opacity = 0.7;
        this.$focus.appendChild($div);
        //console.log("Reference: " + $div.style.top + "," + $div.style.left);
    }
    $.Figleaf.prototype.annotation = function(pos, str) {
        var $div = document.createElement("div");
        $div.innerHTML = "<a target='_new' title='hover for note' alt='hover for note' style='font-size:12px;padding:0 2 0 2px;line-height:10px;margin-right:2px;text-decoration:none;color:#000' href='#open-note'><b>&#10149;</b></a>";
        $div.style.position = "absolute";
        $div.style.top = SCANR.page_h * pos;
        $div.style.left = "5";
        $div.style.opacity = "0.7";
        var $div2 = document.createElement("div");
        $div2.style.position = "absolute";
        $div2.style.top = SCANR.page_h * pos;
        $div2.style.left = "25";
        $div2.style.padding = "10px";
        $div2.style.border = "1px solid #000000";
        $div2.style.backgroundColor = "#FFFFFF";
        $div2.style.width = SCANR.page_w - 100;
        $div2.style.display = "none";
        $div2.innerHTML = decodeURIComponent(str);
        str2 = $div2.textContent;
        $div2.innerHTML = str2;
        function showNote(ev) {
            ev.preventDefault();
            this.style.display = (this.style.display=="none") ? "block" : "none";
            return false;
        }
        $div.onmousedown = showNote.bind($div2);
        this.$focus.appendChild($div2);
        this.$focus.appendChild($div);
        //console.log("Annotation: " + $div.style.top + "," + $div.style.left);
    }
    $.Figleaf.prototype._handle_scroll = function(ev) {
        var page = this.$focus.scrollTop / SCANR.page_h;

        // Clear & draw position on canvas 
        this.$canvas.setAttribute("width", this.width);
        this.$canvas.setAttribute("height", this.height);
        var ctx= this.$canvas.getContext("2d");
        ctx.strokeStyle = "red";
        ctx.lineWidth = 4;
        ctx.beginPath();

        var page_pos = this.pageToPos(page);
        var box_pos = this.pageToBoxPos(page);
        ctx.moveTo(page_pos[0], page_pos[1]);
        ctx.lineTo(page_pos[0]+SCANR.th_w, page_pos[1]);
        ctx.stroke();

        ctx.strokeStyle = "red";
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 0.3;
        ctx.lineTo(box_pos[0]+SCANR.page_w, box_pos[1]);
        ctx.lineTo(box_pos[0], box_pos[1]);
        ctx.lineTo(page_pos[0], page_pos[1]);
        ctx.stroke();

        // Move box
        this.$focus.style.left = box_pos[0];
        this.$focus.style.top = box_pos[1];

        // Fill in images
        var page_start = Math.floor(page);
        [page_start, page_start+1].forEach(function(p) {
            var $div = this.page_containers[p];
            if($div.children.length == 0) {
                var $img = document.createElement("img");
                $img.src = this.basepath + "x" + SCANR.page_h + "-" + p + ".jpg";
                //$img.style.width = "700";
                $img.style.height = SCANR.page_h;
                $div.appendChild($img);
            }
        }.bind(this));
    }
    $.Figleaf.prototype.getPage = function() {
        return this.$focus.scrollTop / SCANR.page_h;
    }
    $.Figleaf.prototype._handle_keypress = function(ev) {
        return;
        if (!this._has_focus) return;
        var t = this;
        if (ev.keyCode == 27) { // escape (hide window)
            this._has_focus = false;
            this.$focus.style.display = "none";
            return false;
        }
    }
    $.Figleaf.prototype._handle_dblclick = function(ev) {
        ev.preventDefault();
        //console.log(this.$canvas);
        //console.log(ev);
        var page = this.$focus.scrollTop / SCANR.page_h;
        var box_pos = this.pageToBoxPos(page);
        var pdf_pos = _el_offset(this.$pdf);
        var click_x = ev.clientX - pdf_pos.left;
        var click_y = ev.clientY - pdf_pos.top;
        var x = click_x - box_pos[0];
        var y = click_y - box_pos[1];
        console.log('click: x:'+x+', y:'+y);
    } 
    // util
    var _el_offset = function( el, fixed ) {
        // http://stackoverflow.com/questions/442404/dynamically-retrieve-html-element-x-y-position-with-javascript
        var _x = 0;
        var _y = 0;
        while( el && !isNaN( el.offsetLeft ) && !isNaN( el.offsetTop ) ) {
            _x += el.offsetLeft - el.scrollLeft;
            _y += el.offsetTop - el.scrollTop;
            if(!fixed) {
                el = el.offsetParent;
            }
            else {
                el = null;
            }
        }
        return { top: _y, left: _x };
    }

})(window);
