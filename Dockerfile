# syntax=docker/dockerfile:1
# Use PUBLIC Red Hat UBI registry (no authentication required)
FROM --platform=linux/amd64 registry.access.redhat.com/ubi10/ubi:latest

# Install Python runtime and pip
RUN dnf -y install --setopt=install_weak_deps=0 --nodocs \
      python3.12 \
      python3.12-pip && \
      dnf -y clean all

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN python3.12 -m pip install -r /tmp/requirements.txt && \
    rm -rf /root/.cache/pip

# Copy application code
COPY proxy.py /opt/app/proxy.py
COPY mockbin /opt/app/mockbin

USER 1001
WORKDIR /opt/app
ENV PYTHONPATH=/opt/app
ENV PATH="/usr/local/bin:/usr/bin:${PATH}"

# Run gunicorn as Python module
CMD ["/usr/bin/python3.12", "-m", "gunicorn", "--bind", "0.0.0.0:8080", "proxy:app_factory", "--worker-class", "aiohttp.GunicornWebWorker", "--access-logfile", "-"]
