+++
date = "2017-06-06T20:04:20-04:00"
draft = false
title = "Kubernetes Learning Notes - Part 5 - Horizontal Scaling and Rolling Upgrade"
categories = ["kubernetes"]

+++

Some of the promises of Kubernetes are scaling and rolling upgrades. In this blog post, we're going to try these out for our service to see how easy it is to achieve these operations which are otherwise difficult to do without a container orchestration tool.

Horizontal Scaling
==================

When we wrote the [manifest]({{< relref "2017-05-29-kubernetes-learning-notes-part-2-stateful-service.md" >}}) for `overmind` deployment, we specified that we want 3 replicas of pods for this deployment. We can scale up the number of replicas to handle increased traffic by using `kubectl scale` command:

    $ kubectl scale --replicas=5 deployment/overmind

Output:

    deployment "overmind" scaled


Now verify that we should have 5 replicas of the overmind pod running:

    $ kubectl get pods -l app=overmind
    NAME                       READY     STATUS    RESTARTS   AGE
    overmind-762504672-1cr20   1/1       Running   1          1d
    overmind-762504672-j7lt2   1/1       Running   0          1m
    overmind-762504672-lpf6h   1/1       Running   1          1d
    overmind-762504672-rc3m8   1/1       Running   1          1d
    overmind-762504672-sw3fr   1/1       Running   0          1m

Notice we used `-l app=overmind` to select only the pods matching the label `app=overmind`.

Scaling down a deployment is just as important as scaling up. It allows for more resources to be made available to services that need them. Scaling down is as simple as specifying `--replica=N` where `N` is less than the current number of replicas.

    $ kubectl scale --replicas=1 deployment/overmind
    deployment "overmind" scaled

If you run `kubectl get pods` right away, chances are you will catch a glimpse of Kubernetes shutting down excess containers (notice the "Terminating" status):

    kubectl get pods -l app=overmind
    NAME                       READY     STATUS        RESTARTS   AGE
    overmind-762504672-1cr20   0/1       Terminating   1          1d
    overmind-762504672-lpf6h   1/1       Running       1          1d
    overmind-762504672-sw3fr   0/1       Terminating   0          7m

Eventually, the system should converge to the desired state:

    $ kubectl get pods -l app=overmind
    NAME                       READY     STATUS    RESTARTS   AGE
    overmind-762504672-lpf6h   1/1       Running   1          1d

Okay, this is scaling in a nutshell. As you can see, it's super easy to scale up and down stateless deployments. Kubernetes also supports auto-scaling where you can specify the minimum and maximum numbrer of pods for a deployment and have it auto-scale depending on the CPU utilization condition that you have set. See [here](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) for more details.


Rolling Upgrades
================

A rolling upgrade is a deployment strategy whereby a deployment is rolled out to a subset of the pods to the new version and gradually replace the old pods with the new pods. This allows for zero downtime deployment and mitigate the risk of a bad deployment.

In earlier versions of Kubernetes, rolling upgrade of replication controllers is done through a separate sub-command `rolling-update`, but since the introduction of `Deployment`, rolling update becomes a strategy for the deployment. No special command is needed, instead, you simply apply the deployment with the strategy and the deployment controller takes care of doing rolling updates.

Put the following in `overmind-deployment-04.yaml`:

```yaml
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
    name: overmind
spec:
    replicas: 3
    strategy:
        type: RollingUpdate
        rollingUpdate:
            maxSurge: 1
            maxUnavailable: 1
    minReadySeconds: 5
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

As you can see, we've added two more keys for the spec:

```yaml
    strategy:
        type: RollingUpdate
        rollingUpdate:
            maxSurge: 1
            maxUnavailable: 1
    minReadySeconds: 5
```

* `maxSurge`: the maximum amount of pods more than the desired number of pods. This can be a number of a percentage. e.g., we have replicas set to 3. With `maxSurge` set to 1, the maximum number of pods during the upgrade process will be at most 4.
* `maxUnavailable`: the maximum amount of pods that can be unavailable during the upgrade process. Also can be an absolute number of a percentage.
* `minReadySeconds`: Kubernetes will wait this amount of time until the next pod creation.

To cause the rolling update, we can update the deployment image to point to an "upgraded" version. We can update our service to use the `kevinjqiu/overmind:2` image, since the currently deployed version is `kevinjqiu/overmind:1`.

Before we update the deployment, let's open up a separate terminal and run:

    while true; do curl $(minikube service overmind --url)/_health; sleep 0.2; done

    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    ...

This way, we are watching the `_health` endpoint to see the currently deployed version.

Now, let's trigger a deployment:

    kubectl set image deployment/overmind overmind=kevinjqiu/overmind:2
    deployment "overmind" image updated

Switch to the terminal where we have the curl command running. We can see something like this:

    ...
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"1.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    {"health":{"version":"2.0.0","brain":"ok"}}
    ...

As you can see, during the cut over, some requests were load-balanced to the new pods where others are still on the old version. Eventually, the cluster state converges to the desired state, which is the new version of the service, but the deployment is done in a rolling manner, upgrading one pod at a time.

For more information, including rolling back and deployment history, see [here](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).
