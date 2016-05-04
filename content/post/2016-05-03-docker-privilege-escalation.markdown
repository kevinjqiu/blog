+++
date = "2016-05-03T22:52:41-04:00"
draft = false
title = "Docker...root...root...Docker (a.k.a. the docker group is a backdoor)"
categories = ["docker", "security"]

+++

While working with docker related stuff and when I use volume mount to a subdir of my home dir, I always come across the issue of the container littering folders with `root:root` permission in my home folder and then I have to `sudo rm ...` it, for example:

    docker run -d $(pwd)/data:/var/lib/mysql/data mysql

It always annoys me but today, it came to me like an epiphany that this is actually a pretty severe security vulnerability.

At `$DAYJOB`, our build machines and staging hosts are all locked down, so we developers don't have `sudo` privilege to run anything **except** `/usr/bin/docker`, so it's `/etc/sudoers` file have something to the effect of:

   %dev            ALL =(root) NOPASSWD: /usr/bin/docker

This is fine and dandy for other commands, but with `docker`, when you run it with `sudo`, you *are* essentially `root`, inside the container and outside. I thought: what if I create an image, and volume mount `/` into the image? Wouldn't that give me root privilege to everything?

A quick proof of concept proved my suspicion:

    $ docker run -it --rm -v /:/mnt alpine /bin/sh
    / # chroot /mnt
    root@0a327dad801b:/# ls /
    bin   config   dev  home        initrd.img.old  lib64  logs        media  opt   root  sbin     srv  syslog-logs  usr  vmlinuz
    boot  content  etc  initrd.img  lib             local  lost+found  mnt    proc  run   selinux  sys  tmp          var  vmlinuz.old

Hey, I have a *root shell* on the host machine where my user account has only limited permissions. Once I'm root, the possibility is endless: I can `cd` into `/home/opsuser`, and insert an ssh key I own to their `~/.ssh/authorized_keys` file and suddenly I can `ssh` as that user without this docker backdoor. I can setup a MITMproxy and capture all traffic on the host. I can inspect the log files I'm not suppsed to see, etc etc etc. Of course I'm not going to do that, but just thinking of it gives me chills, and what if some rogue employee discovers this and either steals my account credentials or impersonates me?

Anyhow, I thought that was quite a revelation, and was about to email security@docker.com, until I searched online. Apparently, this is a [known](http://reventlov.com/advisories/using-the-docker-command-to-root-the-host) [security vulnerability](https://fosterelli.co/privilege-escalation-via-docker.html) that Docker does not consider as such. Once again, the Internet beat me to it :(
