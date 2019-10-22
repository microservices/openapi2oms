FROM        python:3.7-alpine

RUN         mkdir /app
ADD         requirements.txt /app
RUN         pip install -r /app/requirements.txt
RUN         mkdir /app/openapi2oms
ADD         . /app
WORKDIR     /app
RUN         python setup.py install

ENTRYPOINT  ["python", "-m", "openapi2oms.Service"]
