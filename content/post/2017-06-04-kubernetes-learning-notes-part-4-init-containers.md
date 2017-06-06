+++
date = "2017-06-04T23:14:20-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 4 - Service Bootstrapping with Init Containers"
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

For the overmind service, we have two bootstrap tasks:

* Create a user:

```bash
curl -XPUT http://$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/_config/admins/$COUCHDB_USERNAME -d\""$COUCHDB_PASSWORD\"" || true
```

* Create the database:

```bash
curl -XPUT http://$COUCHDB_USERNAME:$COUCHDB_PASSWORD@$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/zerglings || true
```

One important note here is that the script needs to be [idempotent](https://en.wikipedia.org/wiki/Idempotence#Computer_science_meaning), meaning that if you run the script multiple times, it always yields the same result. This is because Kubernetes may move (kill and respawn) pods to different nodes when the current node no longer satisfies the requirement of the pod.

The `|| true` bit here is to prevent the request from failing if the init container has been executed before. There are many more elegant solutions here, but the focus here is to demonstrate the init container concept, so I opted for the simplest working solution.

Since the only executable required by this script is `curl`, we can use a simple [curl](https://hub.docker.com/r/byrnedo/alpine-curl/) container.


Update Deployment Manifest
==========================

Save the following as `overmind-deployment-03.yaml`.

```yaml
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
    name: overmind
spec:
    replicas: 3
    template:
        metadata:
            labels:
                app: overmind
                tier: web
        spec:
            containers:
                - name: overmind
                  image: kevinjqiu/overmind:1
                  imagePullPolicy: Always
                  env:
                      - name: OVERMIND_HTTP_ADDR
                        value: "0.0.0.0:8080"
                      - name: COUCHDB_USERNAME
                        value: admin
                      - name: COUCHDB_PASSWORD
                        valueFrom:
                            secretKeyRef:
                                name: couchdb-password
                                key: password
            initContainers:
                - name: init-overmind-create-user
                  image: byrnedo/alpine-curl
                  command: ['sh', '-c', 'curl -XPUT http://$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/_config/admins/$COUCHDB_USERNAME -d"\"$COUCHDB_PASSWORD"\"']
                  env:
                      - name: COUCHDB_USERNAME
                        value: admin
                      - name: COUCHDB_PASSWORD
                        valueFrom:
                            secretKeyRef:
                                name: couchdb-password
                                key: password
                - name: init-overmind-create-database
                  image: byrnedo/alpine-curl
                  command: ['sh', '-c', 'curl -XPUT http://$COUCHDB_USERNAME:$COUCHDB_PASSWORD@$COUCHDB_SERVICE_HOST:$COUCHDB_SERVICE_PORT/zerglings']
                  env:
                      - name: COUCHDB_USERNAME
                        value: admin
                      - name: COUCHDB_PASSWORD
                        valueFrom:
                            secretKeyRef:
                                name: couchdb-password
                                key: password
```

This is the same as `overmind-deployment-02.yaml` except that we have another key under `spec`: `initContainers`. The containers specified here are run in sequence, so `init-overmind-create-user` runs before `init-overmind-create-database` container, and the second container is not run until the first one is finished and successful.

Deploy and Verify
=================

Submit the manifest to the cluster:

    kubectl apply -f overmind-deployment-03.yaml

If you currently already have the `overmind` container running in the cluster and has already satisfied the desired number of pods, the deployment controller won't be running the `initContainers` since there is no state change required for the `overmind` pod. To trigger `initContainer`s, let's kill an arbitrary pod:

    kubectl delete pod overmind-1630791992-n269m

This causes the cluster state different from the desired state, and the deployment controller will attempt to bring the state of the cluster to the desired state by creating a new `overmind` pod. This will trigger `initContainer`s being run for that pod.

If you do `watch kubectl get pod`, you can see that the init containers are being run:

    $ kubectl get pods
    NAME                        READY     STATUS     RESTARTS   AGE
    couchdb-0                   1/1       Running    2          6d
    overmind-1630791992-n269m   1/1       Running    0          18h
    overmind-1630791992-q1cjw   0/1       Init:0/2   0          2s
    overmind-1630791992-vhcf0   1/1       Running    0          18h

Now let's verify that our service is fully functional:

    $ curl $(minikube service overmind --url)/zerglings/
    {}

Spawn three zerglings:

    $ curl -XPOST $(minikube service overmind --url)/zerglings/ -d'M'
    {"zergling":{"id":"d9c9df4e-034d-47de-9893-fe42aeae8121","location":{"x":0,"y":0},"facing":"N"}}

    $ curl -XPOST $(minikube service overmind --url)/zerglings/
    {"zergling":{"id":"c4a24574-4ca8-4fbd-93e1-2a648147a71f","location":{"x":0,"y":0},"facing":"N"}}

    $ curl -XPOST $(minikube service overmind --url)/zerglings/
    {"zergling":{"id":"a6dbb870-35d9-472b-8510-49d1d3ec5c93","location":{"x":0,"y":0},"facing":"N"}}

List all zerglings:

    $ curl $(minikube service overmind --url)/zerglings/
    {"zerglings":[{"id":"a6dbb870-35d9-472b-8510-49d1d3ec5c93","location":{"x":0,"y":0},"facing":""},{"id":"c4a24574-4ca8-4fbd-93e1-2a648147a71f","location":{"x":0,"y":0},"facing":""},{"id":"d9c9df4e-034d-47de-9893-fe42aeae8121","location":{"x":0,"y":0},"facing":""}]}

Move a zergling:
    $ curl -XPOST $(minikube service overmind --url)/zerglings/c4a24574-4ca8-4fbd-93e1-2a648147a71f -d'"L"'
    {"zergling":{"id":"c4a24574-4ca8-4fbd-93e1-2a648147a71f","location":{"x":0,"y":1},"facing":"W","commandHistory":["M","L"],"_rev":"2-13159f1b66d1407a791832595f529d49"}}

    $ curl -XPOST $(minikube service overmind --url)/zerglings/c4a24574-4ca8-4fbd-93e1-2a648147a71f -d'"M"'
    {"zergling":{"id":"c4a24574-4ca8-4fbd-93e1-2a648147a71f","location":{"x":-1,"y":1},"facing":"W","commandHistory":["M","L","M"],"_rev":"3-7fbf143f67b969685e755b223470628c"}}

Voila! We have successfully deployed and configured the whole stack on a Kubernetes cluster!

Conclusions
===========

`initContainer`s allow us to run certain managerial tasks before the service container is up and running. It's a perfect spot for bootstrapping your application. Since Kubernetes cluster can kill or spawn a pod as it sees fit, it's important to keep these init containers idempotent.

In the next blog post, we're going to explore some of the key features that made Kubernetes unique: horizontal scaling and rolling upgrade. See you then!
