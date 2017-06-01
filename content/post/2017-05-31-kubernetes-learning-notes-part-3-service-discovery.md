+++
date = "2017-05-31T18:06:20-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 3 - Service Discovery"
categories = ["kubernetes"]

+++

In the last two blog posts, we've set up our [overmind service]({{< relref "2017-05-27-kubernetes-learning-notes-part-1-deployment.md" >}}) and the backend [CouchDB service]({{< relref "2017-05-29-kubernetes-learning-notes-part-2-stateful-service.md" >}}). How would the overmind service find out where the CouchDB service is? That's where [Service Discovery](https://kubernetes.io/docs/concepts/services-networking/service/#discovering-services) comes in.

In Kubernetes there are two ways to do service discovery: environment variables and DNS records.

Environment variables
=====================

Every `Service` deployed in Kubernetes automatically gets a set of environment variables accessible to all pods. e.g., if the service name is `couchdb`, other pods will be getting the environment variables such as the following:

* `COUCHDB_SERVICE_HOST`
* `COUCHDB_SERVICE_PORT`

and so on. See a full list [here](https://kubernetes.io/docs/concepts/services-networking/service/#discovering-services).

The `overmind` service will be getting these environment variables, and since our `overmind` service [look for these environment variables to connect to CouchDb](https://github.com/kevinjqiu/overmind/blob/master/service.go#L180-L181), the overmind service should just work, right?

Let's try it:

    $ curl $(minikube service overmind --url)/_health
    {"health":{"version":"1.0.0","brain":"damaged"}}

Hrm, the "brain" is still "damaged"...What's going on here? As it turns out, when we're using environment variable for service discovery, the order of pod creation matters. In this case, we deployed overmind before CouchDB, so the overmind pods do not have these environment variables after the CouchDB service is deployed.

Let's do a re-deploy of the overmind deployment. We need to change the manifest anyway, since we haven't specified `COUCHDB_USERNAME` and `COUCHDB_PASSWORD` in the overmind pod environment. Open up `overmind-deployment.yaml` and make it look like the following:

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


Notice the added environment variables in the `env` section:

      - name: COUCHDB_USERNAME
        value: admin
      - name: COUCHDB_PASSWORD
        valueFrom:
            secretKeyRef:
                name: couchdb-password
                key: password

Apply the new manifest:

    $ kubectl apply -f overmind-deployment-02.yaml
    deployment "overmind" configured

Aaaaand...

    $ curl $(minikube service overmind --url)/_health
    {"health":{"version":"1.0.0","brain":"ok"}}

DNS
===

The alternative to using environment variables is using the DNS server for discovery. kube-dns is an addon although most Kubernetes distributions have it installed. For minikube, it's also included out-of-the-box:

    $ kubectl get service -n kube-system
    NAME                   CLUSTER-IP   EXTERNAL-IP   PORT(S)         AGE
    kube-dns               10.0.0.10    <none>        53/UDP,53/TCP   4d
    kubernetes-dashboard   10.0.0.234   <nodes>       80:30000/TCP    4d

According to the [documentation](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/), for our CouchDB service in the default namespace, we will have a DNS `A` record for `couchdb.default.svc.cluster.local`.

To demonstrate, let's create a simple deployment:

    $ kubectl run --image alpine test -- sleep 1d

This will run the alpine image and put it to sleep, so we can use `kubectl exec` to run arbitrary commands. Find out the pod id by running: `kubectl get pods | grep test`.

`nslookup` is available in the base `alpine` image. Let's use it to make a DNS query:

    $ kubectl exec -it test-2460215515-gb6ns -- nslookup couchdb.default.svc.cluster.local
    Name:      couchdb.default.svc.cluster.local
    Address 1: 10.0.0.2 couchdb.default.svc.cluster.local

The overmind service also has an A record:

    $ kubectl exec -it test-2460215515-gb6ns -- nslookup overmind.default.svc.cluster.local
    Name:      overmind.default.svc.cluster.local
    Address 1: 10.0.0.61 overmind.default.svc.cluster.local

To DNS service discovery for our overmind service, we'd simply specify the environment variable `COUCHDB_SERVICE_HOST` to `couchdb.default.svc.cluster.local`. The advantage of this setup is that the DNS record acts as a layer of abstraction, so the deployments of CouchDB and overmind services do not have to be in order (at least not for the reason that the Kubernetes service environment variable not available for services started before CouchDB).

Conclusion
==========

Service discovery is an important mechanism for microservice architecture. Kubernetes provides multiple ways of allowing services to discover each other: through environment variables and through DNS records. DNS record approach should be favoured as it is more reliable and less susceptible to dependency.

Next in line to get our overmind service working is to bootstrap the database, including seeding the initial user and creating the database. In the next blog post, we're going to look at how to achieve this using the `initContainer` feature.
