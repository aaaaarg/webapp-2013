(function($) {

    var SCANR_DEFAULTS = {n_cols: 20,
                 th_w: 50,
                 th_h: 72,
                 page_w: 700,
                 page_h: 1000,
                 box_h: 300
                }
    var SCANR = {}
    $.Figleaf = function($el, basepath, opts) {
        this.basepath = basepath;

        SCANR.n_cols = opts.n_cols || SCANR_DEFAULTS.n_cols,
        SCANR.th_w = opts.th_w || SCANR_DEFAULTS.th_w,
        SCANR.th_h = opts.th_h || SCANR_DEFAULTS.th_h,
        SCANR.page_w = opts.page_w || SCANR_DEFAULTS.page_w,
        SCANR.page_h = opts.page_h || SCANR_DEFAULTS.page_h,
        SCANR.box_h = opts.box_h || SCANR_DEFAULTS.box_h;

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
        // capture dragging inside the focus
        this.hls = false;
        this.$focus.ondragstart = this._handle_highlight_start.bind(this);
        this.$focus.onmouseup = this._handle_highlight_end.bind(this);
        // capture double clicks
        //this.$focus.addEventListener("click", this._handle_dblclick.bind(this), false);
        this.$focus.addEventListener("dblclick", this._handle_dblclick.bind(this), false);
        
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
            window.onmousemove = undefined;
            window.onmouseup = undefined;
        }

        this.seek(page + th_start);
        // handle multipage selection
        this._handle_select_section(page, ev.shiftKey);
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
    $.Figleaf.prototype.tint = function(page, ratio, color, $parent) {
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
            if ($parent) {
                $parent.appendChild($div);
            } else {        
                this.$el.appendChild($div);
            }
        }
    }
    // coors should be {x1, y1, x2, y2}
    $.Figleaf.prototype.highlight = function(coors) {
        line_height = SCANR.page_h/65;
        function ok(x) {
            return !isNaN(parseFloat(x)) && isFinite(x);
        }
        function mkhl(x1, y1, x2, y2, $parent) {
            //console.log("drawing: x1:"+x1+" ,y1:"+y1+" ,x2:"+x2+" ,y2:"+y2);
            var $div = document.createElement("div");
            $div.style.width = x2-x1;
            $div.style.height = y2-y1;
            $div.style.backgroundColor = "#FFFF00";
            $div.style.position = "absolute";
            $div.style.top = y1;
            $div.style.left = x1;
            $div.style.opacity = 0.3;
            $parent.appendChild($div);
        }
        if (ok(coors.y1) && ok(coors.y2)) {
            if (!ok(coors.x1)) {
                coors.x1 = 0;
            }
            if (!ok(coors.x2)) {
                coors.x2 = SCANR.page_w;
            }
            var $hl = document.createElement("div");
            //this.seek(coors.y1 - 0.05);
            if (SCANR.page_h*(coors.y2-coors.y1)-line_height<=0) {
                mkhl(coors.x1*SCANR.page_w, SCANR.page_h*coors.y1, coors.x2*SCANR.page_w, SCANR.page_h*coors.y1+line_height, $hl);    
            } else {
                mkhl(coors.x1*SCANR.page_w, SCANR.page_h*coors.y1, SCANR.page_w, SCANR.page_h*coors.y1+line_height, $hl);
                if (SCANR.page_h*(coors.y2 - coors.y1) - 2*line_height>0) {
                    mkhl(0, SCANR.page_h*coors.y1+line_height, SCANR.page_w, SCANR.page_h*coors.y2-line_height, $hl);
                }
                mkhl(0, SCANR.page_h*coors.y2-line_height, coors.x2*SCANR.page_w, SCANR.page_h*coors.y2, $hl);
            }
            this.$focus.appendChild($hl);
            return $hl;
        } else {
            return false;
        }
    }
    // Remove highlight
    $.Figleaf.prototype.unhighlight = function($hl) {
        if ($hl) {
            this.$focus.removeChild($hl);
        }
    }
    $.Figleaf.prototype.goto_reference = function(str) {
        function isok(n) {
            return (!isNaN(parseFloat(n)) && isFinite(n));
        }
        n = str.split('-');
        if (n.length==1) {
            n1 = n[0].split(',');
            if (n1.length==2 && isok(n1[1])) {
                this.seek(n1[1]);
            } else if (isok(n1[0])) {
                this.seek(n1[0]);
            }
        } else if (n.length==2 ) {
            n0 = n[0].split(',');
            n1 = n[1].split(',');
            if (n0.length==2 && n1.length==2) {
                this.highlight({x1:n0[0], y1:n0[1], x2:n1[0], y2:n1[1]});
                this.seek(n0[1]);
            } else {
                this.highlight({x1:false, y1:n0[0], x2:false, y2:n1[0]});
                this.seek(n0[0]);
            }
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
    $.Figleaf.prototype.pointer = function(opts) {
        var x = opts.x || 0.98,
        y =  opts.y || false,
        src = opts.src || "",
        href = opts.href || false,
        txt = opts.title || "open";
        if (!x || !y) return; // bad coors
        var $div = document.createElement("div");
        $div.className = "circle";
        $div.style.position = "absolute";
        $div.style.top = SCANR.page_h * y - 10;
        $div.style.left = SCANR.page_w * x - 10;
        if (src!="") {
            var $glance = document.createElement("div");
            $glance.className = 'glance';
            var $gimg = document.createElement("img");
            $gimg.src = src;
            $gimg.style.height = SCANR.page_h;
            $f = this.$focus;
            $div.addEventListener("click", function(ev) {
                $glance.style.top = parseInt($f.style.top) - 50;
                $glance.style.left = parseInt($f.style.left);
                $glance.style.display = 'block'; 
            });
            $gimg.addEventListener("click", function(ev) {
                $glance.style.display = 'none'; 
            });
            $glance.appendChild($gimg);
            if (href) {
                $gref = document.createElement("a");
                $gref.href = href;
                $gref.innerHTML = txt;
                $gref.target = "_new";
                $glance.appendChild($gref);
            }
            //
            this.$el.appendChild($glance);
        } else if (href) {
            $div.addEventListener("click", function(ev) {
                window.open(href, '_blank'); 
            });
        }
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
    $.Figleaf.prototype._handle_dblclick = function(ev) {
        ev.preventDefault();
        var ev2 = new CustomEvent("pointer", {
            detail: this._x_y(ev)
        });
        this.$el.dispatchEvent(ev2);
    } 
    $.Figleaf.prototype._handle_highlight_start = function(ev) {
        ev.preventDefault();
        this.hls = this._x_y(ev);
        return false;
    }
    $.Figleaf.prototype._handle_highlight_end = function(ev) {
        ev.preventDefault();
        if (this.hls) {
            var ev2 = new CustomEvent("excerpt", {
                detail: {
                    begin: this.hls,
                    end: this._x_y(ev)
                }
            });
            this.$el.dispatchEvent(ev2);
        }
        this.hls = false;
        return false;
    }
    // Select section is basically highlighting but on the grid, rather than in the focus
    $.Figleaf.prototype._handle_select_section = function(page, shift_pressed) {
        if (shift_pressed) {
            if (this.ss) {
                // end an existing selection
                var ev2 = new CustomEvent("section", {
                    detail: {
                        begin: Math.min(page, this.ss),
                        end: Math.max(page, this.ss)
                    }
                });
                this.$el.dispatchEvent(ev2);
                this.ss = false;
                this.$el.removeChild(this.$ss);
                this.$ss = false;
            } else {
                // start a new selection
                this.ss = page;
                this.$ss = document.createElement("div");
                this.$ss.className = "section-select";
                this.$el.appendChild(this.$ss);
            }
        }
        if (this.$ss) {
            while (this.$ss.firstChild) {
                this.$ss.removeChild(this.$ss.firstChild);
            }
            for(var i=Math.min(page, this.ss); i<=Math.max(page, this.ss); i++) {
                this.tint(i, 0.3, "orange", this.$ss);
            }
        }
    }
    // gets x, y position within the focus for an event
    $.Figleaf.prototype._x_y = function(ev) {
        var page = this.$focus.scrollTop / SCANR.page_h;
        var box_pos = this.pageToBoxPos(page);
        var pdf_pos = _el_offset(this.$pdf);
        var click_x = ev.clientX - pdf_pos.left;
        var click_y = ev.clientY - pdf_pos.top;
        var x = click_x - box_pos[0];
        var y = click_y - box_pos[1];
        var ay = page + y / SCANR.page_h;
        var ax = x / SCANR.page_w;
        return { page: page, x: x, y: y, ax: ax, ay:ay }
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

function openBook($container, opts) {
    var id = opts.id || '1234',
    w = opts.w || 50,
    h = opts.h || 72,
    rows = opts.rows || 20,
    open_to = opts.open_to || false;
    base_path = opts.base;
    // loading message
    var loading = document.createElement('div');
    loading.innerHTML = 'loading... this can take up to 45 seconds<br/>';
    $container.appendChild(loading); 
    var div = document.createElement('div');
    var img = document.createElement('img');
    img.setAttribute('src', base_path+id+'.pdf/'+w+'x'+h+'x'+rows+'.jpg');
    div.appendChild(img);
    $container.appendChild(div); 
    // create the viewer
    var figleaf = new Figleaf(div, base_path+id+".pdf/", {th_w:w, th_h:h, n_cols:rows});
    // remove loading and allow jumping to a reference
    img.addEventListener('load', function() { 
        $container.removeChild(loading);
        if (open_to) figleaf.goto_reference(open_to);
    }, false);
    return figleaf;
}
