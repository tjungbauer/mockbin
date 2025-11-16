FROM registry.redhat.io/ubi10/ubi as base

RUN dnf -y install --setopt=tsflags=nodocs --setopt=install_weak_deps=0 --nodocs\
      python3.12-devel autoconf automake bzip2 gcc-c++ gd-devel gdb git libcurl-devel \
      libpq-devel libxml2-devel libxslt-devel lsof make mariadb-connector-c-devel \
      openssl-devel patch procps-ng npm redhat-rpm-config sqlite-devel unzip wget which zlib-devel \
      python3.12-pip ; \
      yum -y clean all --enablerepo='*'

FROM base as builder
COPY requirements.txt /tmp/requirements.txt
RUN dnf -y --setopt=install_weak_deps=0 --nodocs \ 
      --releasever 10 \
      --installroot /output \
      install \
      glibc glibc-minimal-langpack libstdc++ \
      bash \
      python3.12 python3.12-requests python3.12-dateutil python3.12-packaging ; \
      yum -y clean all --enablerepo='*'

RUN pip3.12 install --prefix=/usr --root /output -r /tmp/requirements.txt

FROM scratch

COPY --from=builder /output /
#COPY --from=base /root/buildinfo /root/buildinfo
COPY proxy.py /opt/app/proxy.py
COPY mockbin /opt/app/mockbin

USER 1001
WORKDIR /opt/app
ENV PYTHON_PATH=/opt/app
ENTRYPOINT [ "/usr/bin/gunicorn" ]
CMD [ "--pythonpath", "/usr/bin/python3.12", "--bind", "0.0.0.0:8080", "proxy:app_factory", "--worker-class", "aiohttp.GunicornWebWorker", "--access-logfile", "-"]
