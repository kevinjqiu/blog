+++
date = "2017-08-31T18:04:20-04:00"
draft = false
title = "Campfire Story - The \"peril\" of `dev`"
categories = ["kubernetes", "gitlab", "story"]
+++

Through out my career, I have investigated and solved numerous bizarre issues. This one is right up there as being one of the weirdest as well as being one of the most hilarious ones when the truth came out in the end.

At $DAYJOB, we are moving piece by piece our services to [Kubernetes](k8s.io). One of such service slated for migration is the [Gitlab runners](https://gitlab.com/gitlab-org/gitlab-ci-multi-runner). If you're not familiar with [Gitlab](https://gitlab.com), it's like Github you can self-host and it boasts a very powerful and flexible CI/CD pipeline. At the centre of the CI/CD pipeline infrastructure is the `gitlab-ci-multi-runner` component. You can run `gitlab-ci-multi-runner` anywhere, register it with Gitlab and you have yourself a build agent that's capable of running builds.

What makes the `gitlab-ci-multi-runner` more interesting is it itself can run inside a kubernetes cluster, thus, it can be scaled up/down easily and we don't have to worry about keeping a static list of gitlab runners.

Running gitlab runners on Kubernetes is relatively easy. They have a [helm chart](https://docs.gitlab.com/ee/install/kubernetes/gitlab_runner_chart.html) which we had to customize heavily, adding support for many configs (such as specifying runner tags) and features (such as de-register runner automatically when the runner pod shuts down), but nothing unsurmountable. Finally I got a successful build of a project on the kubernetes runner and everything is rosy.

So I announced the availability of Kubernetes-backed gitlab runners and ask people to update their projects to use them. However, error reports started coming in on projects in our main development group (`/dev`). When a build is started on their project, it fails right away with the following message:

```
Running with gitlab-ci-multi-runner 9.5.0~beta.39.ge0b8a7b (e0b8a7b)
  on gitlab-runner-python-docker-compose-gitlab-runner-40176365mfghl (f1d98b78)
  Using Kubernetes namespace: default
  Using Kubernetes executor with image [...] ...
  Waiting for pod default/runner-f1d98b78-project-81-concurrent-0l3bq5 to be running, status is Pending
  ERROR: Job failed (system failure): pod status is failed
```

Perplexed, I forked their project into my own group, started a build and everything was fine. What on earth is going on?

The pipeline is run on the **exact** same code (also the same `.gitlab-ci.yml` file). Could there be differences in the project settings? After meticulously comparing and updating the settings of the upstream and my projects, I kicked off a build again, and nope, still failed with the same error. I asked co-workers to fork the same project into their group and trigger a build and guess what, they pass!

At this point, I felt I need to look beneath the surface; beneath what Gitlab UI is providing us. I cordoned off all but one node of the cluster, and scaled the runners down to 1 replica (so all builds will go through that runner on that node).

First, I need to find out what happened exactly to that pod that failed. Unfortunately, when a pod dies, Kubernetes automatically cleans it up faster than I can manually get a hold of the pod's status. Knowing a computer can do things a lot faster than I can type, I quickly wrote down this:

```
while true; do ids=$(docker ps | grep -v ... | grep -v ... | grep -v pause | cut -d' ' -f1); for id in ids; do docker inspect $id; done; sleep 1; done
```

Basically I want to do `docker inspect` on any new containers and output it to stdout which I can grab and analyze later. Having this script running and triggering a build, I got the reason why the container was failing:

```
...
        "State": {
            "Status": "created",
            "Running": false,
            "Paused": false,
            "Restarting": false,
            "OOMKilled": false,
            "Dead": false,
            "Pid": 0,
            "ExitCode": 128,
            "Error": "invalid header field value \"oci runtime error: container_linux.go:247: starting container process caused \\\"no such 
file or directory\\\"\\n\"",
            "StartedAt": "0001-01-01T00:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z"
        },
...
```

Ahh, the dreaded "no such file or directory" error. This usually happens when the container run command cannot be found. What's the container run command? From the same inspect output:

```
...
        "Path": "sh",
        "Args": [
            "-c",
            "if [ -x /usr/local/bin/bash ]; then\n\texec /usr/local/bin/bash \nelif [ -x /usr/bin/bash ]; then\n\texec /usr/bin/bash \nelif 
[ -x /bin/bash ]; then\n\texec /bin/bash \nelif [ -x /usr/local/bin/sh ]; then\n\texec /usr/local/bin/sh \nelif [ -x /usr/bin/sh ]; then\n\t
exec /usr/bin/sh \nelif [ -x /bin/sh ]; then\n\texec /bin/sh \nelse\n\techo shell not found\n\texit 1\nfi\n\n"
        ],
...

```

`sh`! The shell. But wait a sec, if the `sh` cannot be found, how come it works for builds from other groups? I grabbed the same inspect output from a successful build, and compared them with the failed output, the command and args are **exactly** the same. Also, when I `kubectl exec -it POD sh` I did get a shell. Sigh...

Maybe there's something extra going on at the docker daemon level? There's gotta be different requests called on the docker socket, right?

I tuned up the docker daemon logging on that node, rerun the build, and capture the requests hitting the docker daemon. Filtering all the `GET` requests and comparing the rest, there's no discernable difference again.

At this point, I was getting quite frustrated. There's no new lead for me to pursue and it felt like you're a detective watching a case going cold right in front of your eyes.

"Have you checked the kubelet logs?". Someone across the cubical asked. I did check the kubelet logs before but nothing jumped out. It doesn't hurt trying it again, right?

`journalctl -u kubelet -f` and off we go. Triggering a build and watching the wall of text run by. Suddenly, something caught my eye:

```
Aug 25 21:13:51 ip-10-120-10-250.ca-central-1.compute.internal kubelet-wrapper[2380]: ... {CI_REGISTRY_USER gitlab-ci-token nil} {CI_BUILD_ID 19929 nil} {CI_BUILD_REF 9275e3ca5f6d41a6ee2c1abaf59e654b660ef912 nil} {CI_BUILD_BEFORE_SHA 9275e3ca5f6d41a6ee2c1abaf59e654b660ef912 nil} {CI_BUILD_REF_NAME master nil} {CI_BUILD_REF_SLUG master nil} {CI_BUILD_NAME build nil} {CI_BUILD_STAGE build nil} {CI_PROJECT_ID 4 nil} {CI_PROJECT_NAME YYYY nil} {CI_PROJECT_PATH dev/YYYY nil} {CI_PROJECT_PATH_SLUG dev-YYYY nil} {CI_PROJECT_NAMESPACE dev nil} {CI_PROJECT_URL https://XXXX/dev/YYYY nil} {CI_PIPELINE_ID 4543 nil} {CI_CONFIG_PATH .gitlab-ci.yml nil} {CI_PIPELINE_SOURCE push nil} {CI_RUNNER_ID 177 nil} {CI_RUNNER_DESCRIPTION gitlab-runner-kevin-gitlab-runner-3304628716-38wwj nil} {CI_RUNNER_TAGS python-docker-compose, k8s nil} {CI_REGISTRY XXXX nil} {CI_REGISTRY_IMAGE XXXX/dev/YYYY nil} {REGISTRY registry.points.com nil} {APP_IMAGE XXXX/dev/YYYY:4543 nil} {GITLAB_USER_ID 8 nil}] {map[] map[]} [{repo false /dev } {var-run-docker-sock false /var/run/docker.sock } {default-token-f6qcx true /var/run/secrets/kubernetes.io/serviceaccount }] ...
```

In particular, **this**: `{repo false /dev } {var-run-docker-sock false /var/run/docker.sock }...`. By the look of it, it's describing the volume mount of the pod. The name of the volume is `repo` but look at the path. It's `/dev`! The build container declares `/dev` a volume mount for checking out the code repo. This essentially makes the `/dev` folder of the build container empty, which is not going to please the container runtime. Why is it `/dev` though? Could it be that it's checking out the project according to their group name? Running the build on a different project, and lo and behold, the mount point becomes the name of the group of that project!

Tracing through the `gitlab-ci-multi-runner` code, the code repo checkout is at `Config.BuildsDir`. `BuildsDir` happened to be one of the configuration parameter that neither the original chart nor our fork customized:

```
   --builds-dir                                                 Directory where builds are stored [$RUNNER_BUILDS_DIR]
```

The checkout directory is defined to be `$BUILDS_DIR/$GROUP_NAME/$PROJECT_NAME` and since `$BUILDS_DIR` is not specified (empty string), the checkout directory is `/$GROUP_NAME/$PROJECT_NAME` and since `$GROUP_NAME` here is `dev`, thus the hilarity! Fortunately we don't have groups named `proc`, `var` or `etc`!

Added `$RUNNER_BUILDS_DIR` customization to our helm chart, redeploy and now the builds are happy.

There you go. This was seemingly a very complicated issue, but it all came down to a configuration error (or the lack thereof). The moral of the story is don't get hung up on your assumptions. "No such file or directory" doesn't always mean the system cannot find executables. Also, in hindsight, I probably went down to investigate the docker daemon a little too quickly. Probably should have exhausted all kubernetes logs before checking docker daemon requests.

Anyway, this is definitely one of the more memorable issues I've investigated.
