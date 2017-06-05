+++
date = "2017-06-04T23:14:20-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 4 - Init Containers"
categories = ["kubernetes"]

+++

Up until now,  we have [deployed]({{< relref "2017-05-27-kubernetes-learning-notes-part-1-deployment.md" >}}) the overmind service to the Kubernetes cluster, [deployed]({{< relref "2017-05-29-kubernetes-learning-notes-part-2-stateful-service.md" >}}) the backing CouchDB service and wired up the two services through [service discovery]({{< relref "2017-05-31-kubernetes-learning-notes-part-3-service-discovery.md" >}}). 

Web services usually have administerial tasks, such as bootstrapping a database. It's usually a good practice that individual services are responsible for their own data initialization. This is where [initContainers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) come in handy.

Init Containers
===============

Init containers run inside the same pod as your main container (such as the container that runs the microservice), just like any other containers. You may run multiple init containers for a certain pod, however, there are two main distinctions between init containers and regular containers:

* init containers must run till completion
* in the case of multiple init containers, they're run in serial and one must complete successfully before the next one starts

Bootstrap Script
================

For the overmind service, we create a bootstrap script that creates the CouchDB user and the database.

```bash
#! /bin/sh
curl -XPUT http://$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/_config/admins/$COUCHDB_USERNAME -d\""$COUCHDB_PASSWORD\"" || true
curl -XPUT http://$COUCHDB_USERNAME:$COUCHDB_PASSWORD@$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/zerglings || true
```

One important note here is that the script needs to be [idempotent](https://en.wikipedia.org/wiki/Idempotence#Computer_science_meaning), meaning that if you run the script multiple times, it always yields the same result. This is because Kubernetes may move (kill and respawn) pods to different nodes when the current node no longer satisfies the requirement of the pod.

The `|| true` bit here is to prevent the request from failing if the init container has been executed before. There are many more elegant solutions here, but the focus here is to demonstrate the init container concept, so I opted for the simplest working solution.

Since the only executable required by this script is `curl`, we can use a simple [curl](https://hub.docker.com/r/byrnedo/alpine-curl/) container.
