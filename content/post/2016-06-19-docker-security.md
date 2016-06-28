+++
date = "2016-06-19T21:49:51-07:00"
draft = true
title = "Docker Security"
categories = ["docker", "security"]
+++

[DockerCon 2016](http://2016.dockercon.com/) is here and this is the very first day with workshops on various topics. I chose to attend the Docker Security workshop as I'm interested in seeing how Docker tackles some security challenges. This blog post is my notes taken from the workshop.

In order to talk about security, we first have to know how docker works on a higher level to know what to secure. The workshop addresses that question early on. Container security is different from, say, securing a hypervisor, since they work differently. Docker is essentially an abstraction layer on top of [namespaces](http://man7.org/linux/man-pages/man7/namespaces.7.html) and [cgroups](https://en.wikipedia.org/wiki/Cgroups) so we have to talk about security in those contexts. On a higher level, namespaces govern what a container can see, and cgroups govern what a container can use.

# Namespaces

When forking a child process on Linux, you can specify what system resource is shared from the parent process and what is "unshared", and the "unshared" resource becomes the namespace isolation provided by the kernel to the process. Such resources are:
* mount
* UTS
* IPC
* network
* pid
* cgroup
* user
See `man unshare` for more detailed description.

What this means is changes made within a namespace by a process isn't visible to other processes outside of the namespace, which effectively provided process isolation, and made a docker container appears to be like a virtual machine on the surface.

Namespaces appear as files under `/proc/<pid>/ns` folder, e.g.,

```
# ls -l /proc/1/ns
total 0
lrwxrwxrwx 1 root root 0 Jun 28 03:56 cgroup -> cgroup:[4026531835]
lrwxrwxrwx 1 root root 0 Jun 28 03:56 ipc -> ipc:[4026532440]
lrwxrwxrwx 1 root root 0 Jun 28 03:56 mnt -> mnt:[4026532438]
lrwxrwxrwx 1 root root 0 Jun 28 03:56 net -> net:[4026532443]
lrwxrwxrwx 1 root root 0 Jun 28 03:56 pid -> pid:[4026532441]
lrwxrwxrwx 1 root root 0 Jun 28 03:56 uts -> uts:[4026532439]
```

and if you are within a container, can you find out the container id by querying `/proc/1/cgroup` file, which lists the name of the namespaces.

# Cgroups
cgroups, or control groups is a kernel feature that provides resource tracking and limitations for a group of tasks. In docker terms, the docker daemon creates and assigns a cgroup for each running container, and you can set what resource container is able to get, e.g., CPU, memory or pid limits.

e.g., `docker run` takes:

* `--cpuset-cpus`: CPUs in which to allow execution
* `--cpuset-mems`: MEMs in which to allow execution
* `--memory-reservation`: Memory soft limit
* `--pids-limit`: Tune container pids limit

Docker names the cgroup it creates using the container id, so a handy way to find out the container id within the container is to inspect `/proc/1/cgroup` file in the container:

```
root@48b83d3621b5:/proc/1# cat cgroup
9:pids:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
8:cpu,cpuacct:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
7:net_cls:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
6:devices:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
5:memory:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
4:blkio:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
3:freezer:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
2:cpuset:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
1:name=systemd:/docker/48b83d3621b5c176b22885e799e73f2cec6e14d821c83b2ecb4fc73324212631
```

Here the container id is `48b83...`.

# Docker Security Best Practices
## Building The Image
### Use minimal base images
In a secured environment, every image you build has to come from a known and trusted source. The minimal the base image, the narrower the attack surface is going to be. [Alpine Linux](https://www.alpinelinux.org/) has gain significantly in popularity as it's a very minimal Linux distribution. I personally build almost everything from Alpine when I can. The caveat is it's built using [musl libc](https://www.musl-libc.org/) instead of the ubiquitous glibc so your mileage may vary depending on how your code or your dependency rely on specifics of glibc.

### Verify content
In order to build the chain of trust, we want to know where our software dependencies come from when building the image. Different package management systems have ways to verify the authenticity and integrity of the packages you want to install. For example, when using `apt-get` to install software from 3rd party source, always obtain it from the official channel and verify the keys.

```
RUN apt-key adv \
    --keyserver hkp://keyserver.ubuntu.com:80 \
    --recv-keys ... \
    && echo deb http://repository.example.com stable non-free \
    | tee /etc/apt/sources.list.d/example.list
```

