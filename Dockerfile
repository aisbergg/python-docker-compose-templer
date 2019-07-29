FROM jfloff/alpine-python:3.7-slim

ENV WORKDIR /usr/app/docker-templer

WORKDIR ${WORKDIR}

COPY . ${WORKDIR}

RUN python setup.py install && \
    chmod +x ${WORKDIR}/bin/docker-compose-templer

ENTRYPOINT [ "./bin/docker-compose-templer" ]
