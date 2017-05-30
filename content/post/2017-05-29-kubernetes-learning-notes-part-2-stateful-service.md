+++
date = "2017-05-29T20:30:20-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 2 - Deploying Stateful Services"
categories = ["kubernetes"]

+++

In the [last part]({{< relref "2017-05-27-kubernetes-learning-notes-part-1-deployment.md" >}}) of this series, we learned how to do a basic deployment of a stateless service. You may ask what about our CouchDB service? How do we deploy a database which is innately stateful to a Kubernetes cluster. Kubernetes 1.5+ has introduced [Stateful Set](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) feature which makes this possible.


Stateful Sets
=============

According to the docs, a stateful set provides containers with the following:

* stable and unique network identifiers
* stable persistent storage
* ordered, graceful deployment and scaling
* ordered, graceful deletion and termination

For deploying CouchDB, we need to deploy a stateful set of CouchDB containers which allows us to attach a persistent storage to the container so our overmind service does not lose its data.

Persistent Volumes
==================

First we need to define persistent volumes for the cluster. Note that Kubernetes does not manage the life cycle of a persistent volume. Persistent volumes are provisioned out of band, usually a network backed storage system like NFS, Quobyte, Ceph, etc. After the volume is provisioned, you let the cluster know about it by creating a [`PersistentVolume`](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistent-volumes) object in the cluster.

Create a persistent volume
--------------------------

Let's create a persistent volume for our cluster. Since we're dealing with `minikube` which is essentially a single host cluster, let's just create a folder on the host as our storage.

`ssh` into the `minikube` host:

    minikube ssh

Then, create a folder `/tmp/couchdb`:

    mkdir /tmp/couchdb

Create `PersistentVolume` API object
----------------------------------

After we've created a folder on the host, let's create the API object in Kubernetes so the cluster knows about it.

Save the following as `couchdb-pv.yaml`:

	apiVersion: v1
	kind: PersistentVolume
	metadata:
		name: pv-couchdb
	spec:
		capacity:
			storage: 100M
		accessModes:
			- ReadWriteOnce
		persistentVolumeReclaimPolicy: Recycle
		hostPath:
			path: "/tmp/couchdb"

Here, we declare that our persistent volume has the capacity of 100M and can be mounted as read-write by a single node (`ReadWriteOnce`). Bear that `accessModes` here only defines the mode of access supported by this particular persistent volume. An actual volume can only be mounted using a single mode.

Let's create the object using `kubectl`:

    $ kubectl apply -f couchdb-pv.yaml
    persistentvolume "pv-couchdb" created

Verify:

    $ kubectl get pv
    NAME         CAPACITY   ACCESSMODES   RECLAIMPOLICY   STATUS      CLAIM     STORAGECLASS   REASON    AGE
    pv-couchdb   100M       RWO           Recycle         Available                                      4m


Persistent Volume Claims
========================

After we have the persistent volume defined, a container can request such volume by issuing a persistent volume claim. It's similar to pods in the sense that pods can request computing resource (such as CPU and memory) and Kubernetes allocates the pod to a certain node that satisfy such computing resource constraint whereas persistent volume claims request storage resource and the cluster allocates persistent storage to the claim that can satisfy its constraints such as access mode, size and storage class.

Create `PersistentVolumeClaim` API object
---------------------------------------

Let's look at the manifest for a persistent volume claim. Copy the following to `couchdb-pvc.yaml`:

    kind: PersistentVolumeClaim
    apiVersion: v1
    metadata:
        name: pvc-couchdb
    spec:
        accessModes:
            - ReadWriteOnce
        resources:
            requests:
                storage: 10M
        storageClassName: ""

Under `spec`, we define what constraint our persistent volume should satisfy: support RWO access mode and at least 10MB of storage.
Note that we have `storageClassName` set to `""`. Since we did not define the `storageClassName` when creating our `PersistentVolume`, if I do not include `storageClassName: ""` in the spec, this claim will not find any matching volume to bind to. This is a bit counter-intuitive to me. If anyone knows why it behaves as such, please let me know!

Let's create the PVC object in the cluster:

    $ kubectl apply -f couchdb-pvc.yaml
    persistentvolumeclaim "pvc-couchdb" created

Verify:

    $ kubectl get pvc
    NAME          STATUS    VOLUME       CAPACITY   ACCESSMODES   STORAGECLASS   AGE
    pvc-couchdb   Bound     pv-couchdb   100M       RWO                          28s

As you can see, the `status` of the claim is set to "Bound". Let's drill down using `kubectl describe` command:

    kubectl describe pvc pvc-couchdb
    Name:           pvc-couchdb
    Namespace:      default
    StorageClass:
    Status:         Bound
    Volume:         pv-couchdb
    Labels:         <none>
    Annotations:    kubectl.kubernetes.io/last-applied-configuration={"apiVersion":"v1","kind":"PersistentVolumeClaim","metadata":{"annotations":{},"name":"pvc-couchdb","namespace":"default"},"spec":{"accessModes":["Read...
                    pv.kubernetes.io/bind-completed=yes
                    pv.kubernetes.io/bound-by-controller=yes
    Capacity:       100M
    Access Modes:   RWO
    Events:         <none>

We can see that the volume claim is bound to the volume `pv-couchdb` which is the persistent volume we just created.

Managing Secrets
================

When starting the CouchDB container, we can supply `COUCHDB_USER` and `COUCHDB_PASSWORD` environment variables to create the CouchDB user for our application. Obviously it's less than idea to have the naked password sitting in the manifest file. Kubernetes allows us to create [`Secret`](https://kubernetes.io/docs/concepts/configuration/secret/) objects to host these sensitive information and decode them on-demand. Let's look at how to create them.

Suppose we want our CouchDB username and password to be `admin` and `passw0rd`. Password is the sensitive information that we want to encode here.

Create a Secret
---------------

First, create a plain text file to hold the secret:

    echo -n "passw0rd" > password

We use `-n` here to prevent the `password` file to have a trailing `\n`. Create the secret API object using `kubectl`:

    $ kubectl create secret generic couchdb-password --from-file=password
    secret "couchdb-password" created

Verify:

    $ kubectl get secrets
    NAME                  TYPE                                  DATA      AGE
    couchdb-password      Opaque                                1         35s
    default-token-qt6bn   kubernetes.io/service-account-token   3         2d

    $ kubectl describe secret couchdb-password
    Name:           couchdb-password
    Namespace:      default
    Labels:         <none>
    Annotations:    <none>

    Type:   Opaque

    Data
    ====
    password:       8 bytes

We will be referring to the secret later on when we write the pod definition for the stateful set manifest. The user of the cluster is able to decode the secret:

	kubectl get secret couchdb-password -o yaml
	apiVersion: v1
	data:
	  password: cGFzc3cwcmQ=
	kind: Secret
	metadata:
	  creationTimestamp: 2017-05-30T02:54:42Z
	  name: couchdb-password
	  namespace: default
	  resourceVersion: "62147"
	  selfLink: /api/v1/namespaces/default/secrets/couchdb-password
	  uid: 5471c484-44e3-11e7-a163-080027f8c743
	type: Opaque

The data here is base64 encoded. To decode it, simply use `base64 -d`:

    echo cGFzc3cwcmQ= | base64 -d
    passw0rd

Create Stateful Set for CouchDB
===============================

Now we can tie the above concepts all together to create our stateful set manifest. First off, though, we will have to delete our one-off `PersistentVolumeClaim` since we will be defining a persistent volume claim template inside our `StatefulSet`.

    kubectl delete pvc pvc-couchdb

Now, let's create a file `couchdb-statefulset.yaml`:

	kind: StatefulSet
	apiVersion: apps/v1beta1
	metadata:
		name: couchdb
	spec:
		serviceName: couchdb
		replicas: 1
		template:
			metadata:
				labels:
					tier: db
			spec:
				terminationGracePeriodSeconds: 10
				containers:
					- name: couchdb
					  image: couchdb:1.6
					  ports:
						  - containerPort: 5984
							name: http
					  volumeMounts:
						  - name: couchdb-data
							mountPath: /usr/local/var/lib/couchdb
					  env:
						  - name: COUCHDB_USER
							value: admin
						  - name: COUCHDB_PASSWORD
							valueFrom:
								secretKeyRef:
									name: couchdb-password
									key: password
		volumeClaimTemplates:
			- metadata:
				name: couchdb-data
			  spec:
				  accessModes:
					  - ReadWriteOnce
				  resources:
					  requests:
						  storage: 10M
				  storageClassName: ""

Let's disect it section by section. As usual, the `metadata` section specifies the `name` of the stateful set. In the spec section, we want exactly 1 copy of the CouchDB pod running, since we're running with CouchDB 1.6, which is unclustered. If we want, we can have another CouchDB pod running as a backup and setup replication between the two, but it probably deserve a separate post on its own.

Just like `Deployment`s, `Stateful Set`s also requires pod template definition, since it's able to launch multiple replicas of the same pod. Here we want the CouchDB 1.6 pod with a volume mount named `couchdb-data`. This name refers to the `volumeClaim` which we defined later. Basically, for each replica of the pod, we need a volume claim (which uses the `volumeClaimTemplates`) and use the bound persistent volume to create a volume to be used by the container.

Finally, in the `env` section we define the environment variables used by the pod. `COUCHDB_USER` is self-explanatory. `COUCHDB_PASSWORD` however, uses the secret object that we created earlier named `couchdb-password`. To reference it, use `valueFrom.secretKeyRef` and specify the name of the secret object as well as the key of the secret.

Let's submit this manifest to the cluster:

    kubectl apply -f couchdb-statefulset.yaml
    statefulset "couchdb" created

Let's check the state of the various objects this manifest creates.

First, the persistent volume claim object:

    $ kubectl get pvc
    NAME                     STATUS    VOLUME       CAPACITY   ACCESSMODES   STORAGECLASS   AGE
    couchdb-data-couchdb-0   Bound     pv-couchdb   100M       RWO                          35s

The pods:

    $ kubectl get pod
    NAME                       READY     STATUS    RESTARTS   AGE
    couchdb-0                  1/1       Running   0          1m

And the stateful set:

    $ kubectl get statefulset
    NAME      DESIRED   CURRENT   AGE
    couchdb   1         1         1m

CouchDB Service
===============

Now that we have our CouchDB stateful set deployed, we want to access the CouchDB instance. Similar to deployment of replica sets, we need to create a service to give our pods an IP address.

Let's create a service manifest. Save the following as `couchdb-service.yaml`:

	apiVersion: v1
	kind: Service
	metadata:
		name: couchdb
		labels:
			app: couchdb
			tier: db
	spec:
		selector:
			tier: db
		type: NodePort
		ports:
			- port: 5984

This is similar to the service we created in the last post, except we have a different selector (to select the CouchDB pods) and a different exposed port.

Submit it to the cluster:

	$ kubectl apply -f couchdb-service.yaml
	service "couchdb" created

Verify:

    $ kubectl get service
    NAME         CLUSTER-IP   EXTERNAL-IP   PORT(S)          AGE
    couchdb      10.0.0.2     <nodes>       5984:30281/TCP   8s
    kubernetes   10.0.0.1     <none>        443/TCP          2d
    overmind     10.0.0.61    <nodes>       8080:30674/TCP   1d

As explained in the last blog post, for `minikube`, we can get an ingress URL for the service using `minikube service` command:

    $ minikube service couchdb --url
    http://192.168.99.101:30281

We're able to reach the CouchDb instance using that URL:

    $ curl $(minikube service couchdb --url)
    {"couchdb":"Welcome","uuid":"908a9f83f1376705113e6015c26f994a","version":"1.6.1","vendor":{"version":"1.6.1","name":"The Apache Software Foundation"}} 

Let's create a test database:

    $ curl -XPUT http://admin:passw0rd@192.168.99.101:30281/test
    {"ok":true}
    $ curl http://admin:passw0rd@192.168.99.101:30281/test
    {"db_name":"test","doc_count":0,"doc_del_count":0,"update_seq":0,"purge_seq":0,"compact_running":false,"disk_size":79,"data_size":0,"instance_start_time":"1496116727544049","disk_format_version":6,"committed_update_seq":0}

The point of a stateful set is that if the CouchDB pod dies or has to be killed for some reason, the data it previous had will not disappear and will be re-attached to the CouchDB pod once it becomes available again.

Let's kill the CouchDB pod first:

    $ kubectl delete pod couchdb-0
    pod "couchdb-0" deleted

Trying to access the service endpoint will timeout:

    $ curl http://admin:passw0rd@192.168.99.101:30281/test
    ...

Let's re-apply the same manifest to create the pod again:

    $ kubectl apply -f couchdb-statefulset.yaml
    statefulset "couchdb" configured

And make the curl request:

    $ curl http://admin:passw0rd@192.168.99.101:30281/test
    {"db_name":"test","doc_count":0,"doc_del_count":0,"update_seq":0,"purge_seq":0,"compact_running":false,"disk_size":79,"data_size":0,"instance_start_time":"1496116953931670","disk_format_version":6,"committed_update_seq":0}

As you can see, our service is back and the data it previous had intact.

Conclusion
==========

This concludes our tour of the Stateful Set feature of Kubernetes 1.5+. A stateful set is like a replica set, except it provides a couple of guarantees. One of which is it's able to keep a persistent volume claim, which is suited to run workloads like databases.

A persistent storage is provisioned separately from any Kubernetes objects, and is made aware of by the cluster by creating a `PersistentVolume` object.

A persistent volume is able to be "claimed" by a persistent volume claim. Kubernetes is able to match the constraints expressed in the claim object with a persistent volume that satisfies the constraints.

Deploying stateful services to Kubernetes is still full of sharp edges, just because of the nature of database clustering - every database product is likely to have its own way of doing clustering and orchestration.

In the next blog post, we're going to integrate the `overmind` service with the CouchDB service created in this post. See you next time.
