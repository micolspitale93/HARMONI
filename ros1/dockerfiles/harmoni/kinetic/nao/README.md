# NAO bridge image

Place the NAOqi python 2.7 SDK archive (`pynaoqi-python2.7-<version>-linux64.tar.gz`,
downloadable from the Aldebaran / SoftBank Robotics website) in this folder, then build with:

```bash
docker compose -f docker-compose-group-study.yml build harmoni_nao
```

Alternatively pass a download link: `--build-arg NAOQI_SDK_URL=<url>`.
The archive is ignored by git.
