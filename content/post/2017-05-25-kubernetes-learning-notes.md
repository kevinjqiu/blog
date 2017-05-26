+++
date = "2017-05-25T20:47:11-04:00"
draft = true
title = "Kubernetes Learning Notes - Introduction"

+++

Goals
=====

At `$DAYJOB` we're moving away from our homebrew way of deploying and "orchestrating" docker containers to the promise land of Kubernetes. In the next few blog posts, I'm going to document my learning of Kubernetes here by deploying a simple dockerized microservice with a database backend onto a Kubernetes cluster. The tools and concepts I'll be using here are:

* [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
* [Replica Sets](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)
* [Stateful Sets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
* [Services](https://kubernetes.io/docs/concepts/services-networking/service/)
* [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
* Perform Rolling Upgrades
* [Use Helm to deploy](https://github.com/kubernetes/helm)
* Use Helm to manage deployments
* Use [Traefik](https://github.com/containous/traefik) as Ingress Controller

In this series, I will not be talking about administrating a Kubernetes cluster or provisioning one. The Kubernetes architecture is very interesting by itself and a whole series of blogposts could be written to address that. Instead, this series only deals with the usage of a Kubernetes cluster.

I'll be using [minikube](https://github.com/kubernetes/minikube) as the target. I'm fully aware that minikube is in no way shape or form resemble an actual production-grade Kubernetes cluster, but for learning purpose it's an adequate and convenient substitute for an actual cluster.

The minikube version I'll be using is 1.9 which comes with Kubernetes 1.6.


