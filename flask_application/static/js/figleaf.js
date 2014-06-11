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
            this._populate_pages();
            this._has_focus = true;
        }

        this.$focus.scrollTop = page * SCANR.page_h;
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
    $.Figleaf.prototype.reference = function(pos, url, title) {
        function moveAnnotation(ele) {
            alert(ele);
        }
        var $div = document.createElement("div");
        $div.innerHTML = "<a target='_new' title='"+title+"' alt='"+title+"' style='font-size:12px;padding:0 2 0 2px;line-height:10px;margin-right:2px;background-color:#00FF00;border:1px solid #000;text-decoration:none;color:#000' href='"+url+"'><b>&#10095;</b></a><!--<a target='_new' onclick='moveAnnotation(this)' style='text-decoration:none;cursor:pointer;color:#000;font-size:11px;' href='"+url+"'>&#8597;</a>-->";
        //$div.style.backgroundColor = "#00FF00";
        //$div.style.border = "1px solid #000";
        $div.style.position = "absolute";
        $div.style.top = SCANR.page_h * pos;
        $div.style.left = SCANR.page_w - 28;
        $div.style.opacity = 0.7;
        this.$focus.appendChild($div);
        console.log("Reference: " + $div.style.top + "," + $div.style.left);
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
        console.log("Annotation: " + $div.style.top + "," + $div.style.left);
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
                $img.src = this.basepath + "1024x-" + p + ".jpg";
                $img.style.width = "700";
                $div.appendChild($img);
            }
        }.bind(this));
    }
    $.Figleaf.prototype._handle_keypress = function(ev) {
        if (!this._has_focus) return;
        var t = this;
        if (ev.keyCode == 27) { // escape (hide window)
            this._has_focus = false;
            this.$focus.style.display = "none";
            return false;
        }
        parts = this.basepath.split('/');
        md5 = parts[parts.length - 2];
        var page = this.$focus.scrollTop / SCANR.page_h;
        // console.log('key code: ' + ev.keyCode);
        // if(ev.keyCode == 32 || ev.keyCode == 9 || ev.keyCode == 13) { // space, tab, enter
        if (ev.keyCode == 66) { // b(ookmark)
            window.prompt("Bookmark for this page: ", "http://" + window.location.host + '/ref/' + md5 + "#" + page);
        }
        if (ev.keyCode == 65) { // a(nnotation)
            // one can press quote first and create a highlighted annotation
            var note = window.prompt("Click 'OK' to save the selection. You can add a short note if you want.");
            if (note === null || (note === '' && navigator.userAgent.toLowerCase().indexOf('safari') != -1 && !confirm("Just to confirm:\npress 'OK' to save with an empty note\npress 'Cancel' to cancel the whole thing\n\n(Sorry that this is redundant, but it is because of a Safari bug.)"))) {
                this.clip_top = false;
            } else {
                if (this.clip_top) {
                    pos = this.clip_top + "-" + page;
                } else {
                    pos = page;
                }
                var xhReq = new XMLHttpRequest();
                xhReq.onreadystatechange=function() {
                    if (xhReq.readyState==4 && xhReq.status==200) {
                        if (note!='') {
                            if (t.clip_top) {
                                t.annotation(t.clip_top, note);
                            } else {
                                t.annotation(page, note);
                            }
                        }
                        if (t.clip_top) {
                            t.highlight(t.clip_top, page);
                            t.clip_top = false;
                        }
                    }
                }
                xhReq.open("GET", 'http://' + window.location.host + '/ann/' + md5 + '/add/' + pos + '?note=' + encodeURIComponent(note), true);
                xhReq.send(null);
            }
            
        }
        if (ev.keyCode == 82) { // r(eference)
            var urlRegex = new RegExp(/https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)?/gi);
            var url = window.prompt("Paste a reference URL: ");
            if (url.match(urlRegex)){
                var xhReq = new XMLHttpRequest();
                xhReq.onreadystatechange=function() {
                    if (xhReq.readyState==4 && xhReq.status==200) {
                        if (xhReq.responseText==url){
                            t.reference(page, xhReq.responseText, "");
                        } else {
                            alert(xhReq.responseText);
                        }
                    }
                }
                xhReq.open("GET", 'http://' + window.location.host + '/ref/' + md5 + '/add/' + page + '?url=' + encodeURIComponent(url), true);
                xhReq.send(null);
            } else {
                console.log("bad url: " + url);
            }
        }
        if (ev.keyCode == 219) { // [ (for the beginning)
            this.clip_top = page;
        }
        if (ev.keyCode == 221) { // ] (for the end)
            //var page = this.$focus.scrollTop / SCANR.page_h + SCANR.box_h / SCANR.page_h;
            window.prompt("Bookmark for this clip: ", window.location.host + '/clip/' + md5 + "/" + this.clip_top + "-" + page + ".jpg");
        } 
        if (ev.keyCode == 222) { // ' (the first time opens the clip, the second time closes it)
            page = Math.round( page * 100 ) / 100
            if (this.clip_top) {
                parts = this.basepath.split('/');
                md5 = parts[parts.length - 2]
                window.prompt("Bookmark for this clip: ", "http://" + window.location.host + '/ref/' + md5 + "#" + this.clip_top + "-" + page);
                this.clip_top = false;
            } else {
                this.clip_top = page;
            }
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
