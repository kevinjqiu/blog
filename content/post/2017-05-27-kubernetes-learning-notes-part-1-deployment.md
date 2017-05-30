+++
date = "2017-05-27T17:49:21-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 1 - Deployment"
categories = ["kubernetes"]

+++

Welcome to the first part of my Kubernetes learning notes series. In this blog post, I'm going to record my learning experience for deploying the [overmind](https://github.com/kevinjqiu/overmind) web service to a Kubernetes cluster.

The overmind web service is a simple and contrived microservice for managing zerglings. Don't worry if you're not a starcraft fan. The details of the web service doesn't really matter. The web service has a couple of endpoints, some of which involve talking to a database.

Pre-requisites
==============

First, we need to install `kubectl` - the Kubernetes client CLI tool. Please follow the instruction [here](https://kubernetes.io/docs/tasks/tools/install-kubectl/).

Then we will need to setup a local testing cluster. For that, we use [minikube](https://github.com/kubernetes/minikube) - a tool that spins up a single-node kubernetes instance on your local machine via virtualbox (or other hypervisor). Please refer to the minikube [README](https://github.com/kubernetes/minikube/blob/master/README.md) for how to set it up and run it locally.

After you downloaded the minikube binary and put it in your `$PATH`, run `minikube start`:

    Starting local Kubernetes v1.6.0 cluster...
    Starting VM...
    SSH-ing files into VM...
    Setting up certs...
    Starting cluster components...
    Connecting to cluster...
    Setting up kubeconfig...
    Kubectl is now configured to use the cluster.

Now your "cluster" is up and running and your `kubectl` is configured to use the minikube context:

    $ kubectl get node
    NAME       STATUS    AGE       VERSION
    minikube   Ready     3d        v1.6.0

Pods, Replica Sets, Deployments
================================

Pods, replica sets and deployments are core concepts involved in deploying a container to our cluster.

Pod
---

A [Pod](https://kubernetes.io/docs/concepts/workloads/pods/pod-overview/) is the most basic building block of a Kubernetes. A pod represents a running process on your cluster. In container terms, a pod is one or more containers the need to work together. They containers in the same pod share the same networking namspace, which means container A can talk to container B in the same pod via `localhost`. In the overmind service example, we will be deploying the overmind docker container as a pod in the cluster.

Replica Set
-----------

A [Replica Set](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/) is a kubernetes "controller" that ensures at any given time, the correct number of "replicas" of a pod is present in the cluster. For example, if I declare that the `overmind` pod has a replica of 3. The replica set controller makes sure that there are 3 `overmind` pods running in the cluster. If for some reason, one pod died, the controller will spin up another pod in the cluster to bring the total number of replicas to 3.

Deployment
----------

A [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) declares the desired state for pods or replica sets. For example, you can declare that the deployment should use the rolling upgrade strategy so we can have zero-downtime deployment.

Let's start by creating a deployment manifest for our `overmind` service.

Deployment Manifest
===================

Let's start writing a deployment manifest for our service.

Save the following as `overmind-deployment.yaml`.

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
					  env:
						  - name: OVERMIND_HTTP_ADDR
							value: "0.0.0.0:8080"

The yaml file here describes the `Deployment` object. The deployment object declares that we want 3 replicas of the `overmind` pod, and the pod definition is encoded below in the `template` section. The schema for `template` is the same as the schema for [pod](https://kubernetes.io/docs/concepts/workloads/pods/pod/).

Here we declare that each pod will include a single container using the `kevinjqiu/overmind:1` image. We also specify the environment variable for our pod which defines the bind address for our service.

Start Deployment
================

After we have the deployment manifest, let's start a deployment by using the `kubectl` command:

    $ kubectl apply -f overmind-deployment.yaml
    deployment "overmind" create d

Let's verify the deployment object is correctly created:

    $ kubectl get deployment
    NAME       DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
    overmind   3         3         3            3           1m

The deployment manifest will also create another two types of objects as discussed above: pods and replica sets. Let's verify that:

    $ kubectl get pods
    NAME                       READY     STATUS    RESTARTS   AGE
    overmind-581439581-h3f3f   1/1       Running   0          3m
    overmind-581439581-hbq0g   1/1       Running   0          3m
    overmind-581439581-szkk5   1/1       Running   0          3m

    $ kubectl get rs
    NAME                 DESIRED   CURRENT   READY     AGE
    overmind-581439581   3         3         3         4m

So far so good. As you can see, we have 3 replicas of the pod running in the cluster. Each pod does have its own ip address. They can be shown using `kubectl get pods -o wide` command:

    $ kubectl get pods -o wide
    NAME                       READY     STATUS    RESTARTS   AGE       IP           NODE
    overmind-581439581-h3f3f   1/1       Running   0          6m        172.17.0.5   minikube
    overmind-581439581-hbq0g   1/1       Running   0          6m        172.17.0.6   minikube
    overmind-581439581-szkk5   1/1       Running   0          6m        172.17.0.4   minikube

From your host, there isn't a route to get to those ip addresses but they are reachable on the hosts in the cluster.

To prove that, let's ssh into the minikube instance:

    minikube ssh

Try `curl`ing one of these ip addresses:

    $ curl 172.17.0.5:8080/_health
    {"health":{"version":"1.0.0","brain":"damaged"}}

So there it is. Our pod is up and running correctly.

Services
========

Our pods may have been deployed correctly in the cluster, but there are a couple of problems:
* the pods are not load balanced
* if we setup load balancer externally, and if pods die and the replica set (controller) spawns a new pod, how are we to have the load balancer update its backends?

This is where [service](https://kubernetes.io/docs/concepts/services-networking/service/) comes in. A service is an abstraction which defines the access to a logical group of pods. Defining a service will give the pods a unified [(virtual) IP](https://kubernetes.io/docs/concepts/services-networking/service/#virtual-ips-and-service-proxies) address, distribute the load and watches for pod changes so it can add/remove pods from its available backends.


Service Manifest
================

Let's go ahead and make a service manifest. Create a file `overmind-service.yaml`:

	apiVersion: v1
	kind: Service
	metadata:
		name: overmind
		labels:
			app: overmind
			tier: web
	spec:
		selector:
			app: overmind
			tier: web
		type: NodePort
		ports:
			- port: 8080

A service uses `selector` to collect the pods and load balance them. In the deployment manifest, we declare that the `overmind` pods have the labels `app=overmind` and `tier=web`. Here, we use this selector in the `selector` section of the `spec` to declare that the service should select these pods.

We also specify `type: NodePort`. This defines the way we "publish" our service. `NodePort` is a simple mechanism that each node in the cluster will proxy the same port into the service. The other allowed type is `LoadBalancer` which allows you to integrate Kubernetes with a Cloud Provider and setup load balancer in the cloud (e.g., ELB).

Create the Service
==================

Let's apply the manifest and test it out.

    $ kubectl apply -f overmind-service.yaml
    service "overmind" created

Verify that the service exists:

    $ kubectl get svc -o wide
    NAME         CLUSTER-IP   EXTERNAL-IP   PORT(S)          AGE       SELECTOR
    kubernetes   10.0.0.1     <none>        443/TCP          6h        <none>
    overmind     10.0.0.61    <nodes>       8080:30674/TCP   8m        app=overmind,tier=web

Keep in mind that these ip addresses are still cluster-wide. There isn't a route to those ip addresses that you can `curl` with. To allow traffic from outside of the container, we need to setup `Ingress` but that's a topic for later. Fortunately, `minikube` has a convenient way for us to allow traffic into the container. Use the following command:

    $ minikube service --url overmind
    http://192.168.99.101:30674

Now we can use this url to access the overmind service deployed on Kubernetes:

    $ curl $(minikube service --url overmind)/_health
    {"health":{"version":"1.0.0","brain":"damaged"}}

Conclusion
==========

In this blog post, we've gone through the basics of how to deploy to a Kubernetes cluster using `deployment`s with `pod`s and `replica set`s. We also used `service` to abstract the access of these pods.

You may notice in the above `curl` output that it says the `brain` of `overmind` is "damaged". This is due to the fact that we haven't deployed the "brain" - CouchDB to the cluster yet. Deploying CouchDB (a stateful service) involves container volumes, persistent volumes and claims, stateful sets and a little bit of secret management. Stay tuned for the next blog post where I'll be writing about my learning experience with these topics. Ciao!
