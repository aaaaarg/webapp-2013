Grrrr
=====

A platform for collective archives.

Docker
------

To get up and running using docker, see [readme-docker.md](readme-docker.md).

Prerequisites
-------------

Install the following on your system:

* memcached
* elasticsearch (using the [official repositories](https://www.elastic.co/guide/en/elasticsearch/reference/current/setup-repositories.html) is recommended)
* mongodb
* curl
* git
* python
* pip
* [VirtualEnv](https://virtualenv.readthedocs.org/en/latest/) and [VirtualEnvWrapper](http://www.doughellmann.com/docs/virtualenvwrapper/)
* development libraries for python, libjpeg8, libxml2, libxslt1, zlib1g (needed for python libraries to build successfully)

If you are running Ubuntu 14.04, you can install all the above with
these commands. This probably also works on other recent versions of
Ubuntu.

        sudo apt-get install openjdk-7-jdk mongodb elasticsearch memcached curl git python-pip python-virtualenv virtualenvwrapper python-dev libxml2 libxml2-dev libxslt1-dev zlib1g-dev libjpeg8-dev
        # start elasticsearch on startup
        sudo update-rc.d elasticsearch defaults

Installation
------------

1. Clone this repository:

        git clone git@github.com:aaaaarg/webapp-2013.git

2. Change into the cloned directory

        cd webapp-2013

3. Create a new virtualenvironment and switch to it

        mkvirtualenv grrrr
        workon grrrr

4. Install the required python dependencies

        pip install -r requirements.txt
    
5. As a temporary workaround, run this command to get a version of
   Flask-Social that works with the current mongoengine (TODO: this
   didn't work for me; is it still needed?)

        pip install --upgrade https://github.com/mattupstate/flask-social/tball/develop

6. Copy `flask_application/config.py.example` to
   `flask_application/config.py` and edit the settings as appropriate.

        cd flask_application
        cp config.py.example config.py
        vi config.py

7. Create an elasticsearch index named 'aaaarg'.

        curl -XPUT 'localhost:9200/aaaarg?pretty'

8. Populate the database with some data

        python manage.py populate_db

9. Run the development server. You should be able to access the
application at http://localhost:5000/

        # set environment
        export DEV=yes
        # run server
        python manage.py runserver

  If you're running the app from inside a virtual machine and want to
  be able to access it from outside the VM, run this command instead,
  and load use the IP address in the browser, i.e. something like
  http://192.168.1.10:5000/

        python manage.py runserver -t 0.0.0.0


Credit
------

####Non-Python Projects:
* Twitter Bootstrap

####Contributing Projects:
* https://github.com/swaroopch/flask-boilerplate _The project's structure is built from this_
* Flask-Security Example App
* https://github.com/earle/django-bootstrap _uses some template macros_

Usage
-----

##Commands
_Run these commands by using `python manage.py <command>`_


* `reset_db` - Drops all Mongo documents
* `populate_db` - Script to fill the database with new data (either for testing or for initial). You can edit the `populate_data` command in `flask_application/populate.py` (Right now it is set up to add Users.)
* `runserver` - Runs a debug server
* Commands included with Flask-Security can be found here: http://packages.python.org/Flask-Security/#flask-script-commands and by looking in `flask_application/script.py`

##Templates
The base template is based off of Django-bootstrap and is found under: `flask_application/templates/bootstrap/layouts/base_navbar_responsive.html`

##Static Content
This project is designed to use CSSMin and Flask-Assets to manage Assets to save on bandwidth and requests. 

You can find this in the `css_bootstrap` block of the layout template. You can also simply edit `static/css/site.css` as that is included in the base setup. 

##Encoding and Decoding Id's
Sometimes you won't want simple URLs revealing the order of the object ids. For example:
    
    http://example.com/users/view/1/

So you can use `encode_id` and `decode_id` found in `flask_application/helpers.py`

So 

        http://example.com/users/view/1/
        
becomes

        http://example.com/users/view/w3c8/



LICENSE &amp; COPYRIGHT
-----------------------

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
