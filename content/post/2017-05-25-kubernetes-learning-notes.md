+++
date = "2017-05-25T20:47:11-04:00"
draft = false
title = "Kubernetes Learning Notes - Introduction"
categories = ["kubernetes"]
+++

Parts
=====

* [Part 1 - Basic Deployment](2017-05-27-kubernetes-learning-notes-part-1-deployment)
* Part 2 - Deploy CouchDB

Goals
=====

At `$DAYJOB` we're moving away from our homebrew way of deploying and "orchestrating" docker containers to the promise land of Kubernetes. To solidify my learning, I'm going to practise what I learn by coming up with a hands-on project deploying a simple dockerized microservice with a database backend onto a Kubernetes cluster. Here are the Kubernetes features and 3rd party tools I foresee I will touch upon:

* [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
* [Replica Sets](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)
* [Stateful Sets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
* [Services](https://kubernetes.io/docs/concepts/services-networking/service/)
* [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
* Perform Rolling Upgrades
* [Use Helm to deploy](https://github.com/kubernetes/helm)
* Use Helm to manage deployments
* Use [Traefik](https://github.com/containous/traefik) as Ingress Controller

Anti-Goals
==========

I will not be touch on administrating a Kubernetes cluster nor provisioning one. The Kubernetes architecture is very interesting by itself and a whole series of blogposts could be written to address that. Instead, this series only deals with the practical usage of a Kubernetes cluster from a beginner's perspective.

Requirements
============

I'll be using [minikube](https://github.com/kubernetes/minikube) as the target. I'm fully aware that minikube is in no way shape or form resemble an actual production-grade Kubernetes cluster, but for learning purpose it's an adequate and convenient substitute for an actual cluster.

The minikube version I'll be using is 1.9 which comes with Kubernetes 1.6.

Overmind
========

The demo project we'll be using here is a highly contrived one consisting of 3 microservices: Overmind, Viper and Zergling. In StarCraft, overmind, viper and zergling are units from the Zerg race. The overmind is the service that the user communicate with to control the swarm. Overmind can be instructed to spawn zerglings through a viper and control the spawned zerglings.

Overmind Service
----------------

Here are the API definitions:

* `GET /_health` - The health of the overmind and its subordinates
* `GET /zerglings` - All zerglings the overmind is aware of and their locations
* `GET /zerglings/<zergling_id>` - Get the status of the specified zergling
* `POST /zerglings/<zergling_id>` - Move the zergling
* `POST /zerglings/` - Spawn a zergling (through **viper** but omitted for simplicity)

You can find the full source code [here](https://github.com/kevinjqiu/overmind).

Storage
-------

Overmind service uses [CouchDB](https://couchdb.apache.org) as its "brain" to keep track of the zerglings and their statuses. We will be deploying a CouchDB instance in the cluster to learn how to use `PersistentVolume`s and `StatefulSet`s.

Okay, I think that's enough intro for now. Tune in for the next blogpost on learning to deploy the overmind service on Kubernetes!
