
FROM ubuntu:16.04

RUN apt-get update && apt-get install -y openjdk-8-jdk curl git python-pip python-virtualenv virtualenvwrapper python-dev libxml2 libxml2-dev libxslt1-dev zlib1g-dev libjpeg8-dev

RUN /bin/bash -l -c "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh \
  && mkvirtualenv grrrr"

COPY requirements.txt /tmp

RUN /bin/bash -l -c "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh \
  && workon grrrr \
  && cd /tmp \
  && pip install -r requirements.txt"

EXPOSE 5000

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app

CMD /bin/bash -l -c "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh \
    && workon grrrr \
    && python manage.py runserver -t 0.0.0.0"
