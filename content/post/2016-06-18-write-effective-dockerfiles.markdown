+++
date = "2016-06-18T10:15:43-04:00"
draft = true
title = "Write Effective Dockerfiles"
categories = ["docker"]
+++

Notes:
Structure Dockerfile so build takes advantage of layer caching
Always use `USER user`
Entrypoint script should use `exec`
