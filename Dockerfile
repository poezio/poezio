FROM alpine:latest
MAINTAINER Mathieu Pasquet <mathieui@mathieui.net>
RUN apk add --update build-base git python3 python3-dev libidn-dev && python3 -m ensurepip && pip3 install --upgrade pip && pip3 install cython pyasn1 pyasn1-modules
WORKDIR /tmp/
ARG version=HEAD
# Don’t ADD local files in order to keep layers at a minimal size
RUN git clone https://lab.louiz.org/poezio/poezio.git poezio-git-dir && \
        cd poezio-git-dir && \
        git archive --prefix="poezio-archive-${version}/" -o /tmp/poezio-archive.tar "${version}" && \
        cd /tmp/ && tar xvf poezio-archive.tar && \
        cd "poezio-archive-${version}" && \
        python3 setup.py install && \
        cd .. && rm -rf /tmp/poezio-* ~/.cache ~/.pip
RUN adduser -D poezio-user
USER poezio-user
WORKDIR /home/poezio-user/
ENTRYPOINT ["poezio"]
