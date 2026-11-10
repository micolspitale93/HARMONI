# NAO bridge: python 2.7 + NAOqi SDK, no ROS.
#
# The NAOqi SDK cannot be redistributed. Place "pynaoqi-python2.7-<version>-linux64.tar.gz"
# (Aldebaran / SoftBank Robotics website) in this folder, or build with
#   --build-arg NAOQI_SDK_URL=<url of the tar.gz>
# To try the bridge without robot and SDK: --build-arg NAOQI_SDK=none and NAO_MOCK=1.
FROM python:2.7-slim

ARG NAOQI_SDK=required
ARG NAOQI_SDK_URL=""
COPY . /tmp/naoqi/
RUN set -e; cd /tmp/naoqi; \
    TARBALL=$(ls pynaoqi-python2.7-*.tar.gz 2>/dev/null | head -n 1 || true); \
    if [ -z "$TARBALL" ] && [ -n "$NAOQI_SDK_URL" ]; then \
        python -c "import sys, urllib; urllib.urlretrieve(sys.argv[1], 'pynaoqi.tar.gz')" "$NAOQI_SDK_URL"; \
        TARBALL=pynaoqi.tar.gz; \
    fi; \
    if [ -n "$TARBALL" ]; then \
        mkdir -p /opt/naoqi && tar -xzf "$TARBALL" -C /opt/naoqi --strip-components=1; \
    elif [ "$NAOQI_SDK" != "none" ]; then \
        echo "ERROR: NAOqi SDK not found, see ros2/nao_bridge/README.md"; exit 1; \
    fi; \
    mkdir -p /app && cp nao_bridge.py /app/ && rm -rf /tmp/naoqi
ENV PYTHONPATH=/opt/naoqi/lib/python2.7/site-packages \
    LD_LIBRARY_PATH=/opt/naoqi/lib \
    BRIDGE_PORT=8765
EXPOSE 8765
CMD ["python", "/app/nao_bridge.py"]
