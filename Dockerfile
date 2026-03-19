# syntax=docker/dockerfile:1@sha256:b6afd42430b15f2d2a4c5a02b919e98a525b785b1aaff16747d2f623364e39b6
# Use PUBLIC Red Hat UBI registry (no authentication required)
# hadolint ignore=DL3029
# Platform flag required for cross-compilation from ARM (Mac M-series) to x86_64
FROM --platform=linux/amd64 registry.access.redhat.com/ubi10/ubi:10.1-1773895909@sha256:17296ded9ab581e9a9019a71e15576c0a99813d8870eb6758e32b5bf93c5ff71

# Install Python runtime and pip
# hadolint ignore=DL3041
# Version pinning not practical for UBI packages - base image version controls package versions
RUN dnf -y install --setopt=install_weak_deps=0 --nodocs \
      python3.12 \
      python3.12-pip && \
      dnf -y clean all

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN python3.12 -m pip install --no-cache-dir -r /tmp/requirements.txt && \
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
