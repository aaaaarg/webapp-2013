
# How to run using Docker

Install docker and docker-compose on your system. Then follow these steps:

1. Clone this repository:

        git clone git@github.com:aaaaarg/webapp-2013.git

2. Change into the cloned directory

        cd /wherever/webapp-2013

3. Copy `flask_application/config.py.docker` to
   `flask_application/config.py` and edit the settings as appropriate.
   Note that the app will access services in other containers using
   the hostnames in `docker-compose.yml`.

        cd flask_application
        cp config.py.docker config.py
        vi config.py

4. Edit `.docker-environment` as appropriate.

5. Build all the services needed, including the app image.

        cd /wherever/webapp-2013
        docker-compose build

6. Run the app.

        docker-compose up

   NOTE: the ports of the containerized services are mapped to your
   host's ports, for convenience of use and debugging. If you already
   have ElasticSearch, MongoDB, or something using port 5000 on your
   host, you'll get errors, and you'll need to adjust the Dockerfile
   accordingly.

   You should now be able to load the app in your browser at http://localhost:5000/

7. Create an elasticsearch index named 'aaaarg'.

        curl -XPUT 'localhost:9200/aaaarg?pretty'

8. Populate the database with some data

        # start a shell in the running container:
        # yours might not be called "webapp2013_app_1",
        # use "docker ps" to find out its name
        docker exec -it webapp2013_app_1 /bin/bash -l
        # use the virtualenv
        workon grrrr
        # run the task
        python manage.py populate_db

That's it!

