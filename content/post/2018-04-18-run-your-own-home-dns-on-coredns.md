---
title: "Run Your Own Home DNS on coredns"
date: 2018-04-18T23:09:59-04:00
draft: true
---

I have been running my home DNS on a pair of RaspberryPi's for some time now.  The main reason for running my own DNS server is to utilize the excellent [pihole](https://pi-hole.net/) project to block 3rd-party ads from being served to my home network.

I [ansiblized](https://github.com/kevinjqiu/home.idempotent.io/tree/master/roles/pihole) the config files.  It has been running great for a couple of months.

Recently, I have acquired an [orangepi](orangepi.org), a RaspberryPi 3 and a new desktop.  Together with my 10+ year old Thinkpad T60p that serves as my home server, my main laptop, and my two original RaspberryPi's, there are way too many IP addresses for me to remember if I need to ssh into them.  This is when the idea of hosting a home DNS zone came to me.  What if I can `ssh monarch.srv.qiu.home` (`srv` for "server")?  I also run many services on my home server including [Emby](emby.media) for media streaming, [Prometheus](prometheus.io) and [Grafana](grafana.org) for monitoring/alerting and graphing server stats, and a [celery](www.celeryproject.org) job that downloads my bank statements periodically, and a [CouchDB](couchdb.apache.org) server that the transactions from the bank statements are being saved to.  Eventually I want to be able to address these services by domain name instead of IP+port, e.g., `emby.svc.qiu.home` or `couchdb.svc.qiu.home`.  I will likely have to add a DNS entry `svc.qiu.home` (`svc` for "service") for my home server running a load balancer / proxy (I'm thinking of using [traefik](traefik.io)) and use virtual host to proxy these services but that's for another day.  Today, I'm just going to setup a hosted zone for `.srv.qiu.home`.

One obvious choice is to add those host name and domain name mappings to `/etc/hosts` file of the DNS servers (my two raspberypi's), but what fun would that be?  Also, setting up a hosted zone with the zone's `SOA` (start of authority) pointing to my own server would allow me to later migrate my DNS to the cloud so I can recursively resolve `.srv.qiu.home` using the public DNS server.  Not that I plan to splash the cash to acquire `.qiu.home` domain, but the know-how is what's important and I do have a handful of domains that I could potentially use.

Another obvious choice is to piggy-back on pihole to let pihole aware of the zone.  Pihole is built on top of [dnsmasq](https://en.wikipedia.org/wiki/Dnsmasq).  I'm not an expert on dnsmasq (or dns for that matter), but after some searching around, it doesn't look like `dnsmasq` supports serving your own zone file.  Most tutorials online use 

Now I came to the conclusion that I need to setup a separate DNS server to serve the zone, and forward queries for other domain names to the pihole servers.  Most online tutorials use [bind9](https://www.isc.org/downloads/bind/).  I followed the [excellent tutorial on digitalocean](https://www.digitalocean.com/community/tutorials/how-to-configure-bind-as-a-private-network-dns-server-on-ubuntu-14-04) and it worked nicely.  I [ansiblized](https://github.com/kevinjqiu/home.idempotent.io/tree/master/roles/bind9) the bind9 solution and everything seems to fall in place.

However, in my last year of immersion in the cloud and kubernetes space, I heard a lot of buzz around [coredns](coredns.io).  CoreDNS is written in Golang and based on [Caddy](caddyserver.com).  I wanted to see if I can implement the same DNS zone using coredns, and hence this blog post is born.

CoreDNS
-------

As mentioned, CoreDNS is a new DNS server implementation written in Golang.  Starting in Kubernetes 1.9+, CoreDNS replaced kube-dns (which is based on dnsmasq) to be **the** DNS solution inside a Kubernetes cluster.

Just like Caddy, CoreDNS is designed to be extensible with [plugins](https://coredns.io/plugins/).  Having native support for Prometheus is a big plus, which means I can hook it into my existing Prometheus infrastructure for monitoring, alerting and dashboarding.

The Big Picture
---------------

[![The Big Picture]](big-picture.png)

We instruct the router to set client's resolver to the RaspberryPi's IP addresses.  The `.0.11` is used as the primary resolver and `.0.12` is the secondary.  Clients (meaning computers/laptops/cell phones/tablets) connected to the router through DHCP are assigned an ip address and given the RaspberryPi's IP addresses as the resolvers.

We don't want to lose the ability to filter ads, so I kept the pihole dnsmasq service but only to run it on a different port.  Then using query forwarding, I can instruct CoreDNS to forward any queries it doesn't handle to the upstream resolver, which is the pihole dnsmasq service in this case.

Getting Started
---------------

Download the CoreDNS binary for your platform.  For first generation RaspberryPi, it's simply `arm` (https://github.com/coredns/coredns/releases/tag/v1.1.1).  Then extract it to somewhere on your `$PATH`.  Now, invoke `coredns` and chances are you will see:

```
$ ./coredns
2018/04/19 04:16:34 listen tcp :53: bind: permission denied
```

That's because it tries to bind to port 53 (the standard DNS port) using an unprivileged user.  We'll deal with that later.  For now, let's run it on a different port for testing.

Barebone Corefile
-----------------

Here's the simplest `Corefile`:

```
.:65353 {
    log
    errors
}
```

* `.:5353` tells CoreDNS where it should bind itself to.  In this case, port 5353 on all interfaces.
* `log` is the [logging plugin](https://coredns.io/plugins/log/), which logs DNS queries requested.
* `errors` enables [error logging](https://coredns.io/plugins/errors/).

Now, run `coredns`:

```
$ coredns
.:65353
2018/04/19 04:25:53 [INFO] CoreDNS-1.1.1
2018/04/19 04:25:53 [INFO] linux/arm, go1.10, 231c2c0e
CoreDNS-1.1.1
linux/arm, go1.10, 231c2c0e
```

Now it's serving DNS requests on port 65353.  Let's try it out using `dig`:

```
$ dig @192.168.0.12 -p 65353 google.com

; <<>> DiG 9.10.3-P4-Ubuntu <<>> @192.168.0.12 -p 65353 google.com
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 10678
;; flags: qr rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 1
;; WARNING: recursion requested but not available

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 4096
;; QUESTION SECTION:
;google.com.                    IN      A

;; Query time: 3 msec
;; SERVER: 192.168.0.12#65353(192.168.0.12)
;; WHEN: Thu Apr 19 00:27:06 EDT 2018
;; MSG SIZE  rcvd: 39
```

There's no answer!  Well, duh, we haven't setup any zone files or forwards so right now this DNS server is next to useless.

This is confirmed by the CoreDNS logs:

```
192.168.0.10:35488 - [19/Apr/2018:04:27:06 +0000] 10678 "A IN google.com. udp 40 false 4096" SERVFAIL qr,rd 40 1.830937ms
19/Apr/2018:04:27:06 +0000 [ERROR 0 google.com. A] plugin/log: no next plugin found
```

Setup Forwarding
----------------

To make it semi-useful, we can forward queries to the pihole dnsmasq service, so after this step, the CoreDNS service becomes essentially a proxy for the pihole's DNS service.

```
.:65353 {
    log
    errors
    forward . 127.0.0.1:15353
}
```

We added the `forward ...` line using the [forward plugin](https://coredns.io/plugins/forward/).  `127.0.0.1:15353` is where the pihole's dnsmasq service is.

Now, let's resolve google.com again:

```
dig @192.168.0.12 -p 65353 google.com

; <<>> DiG 9.10.3-P4-Ubuntu <<>> @192.168.0.12 -p 65353 google.com
; (1 server found)
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 47361
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 4096
;; QUESTION SECTION:
;google.com.                    IN      A

;; ANSWER SECTION:
google.com.             12      IN      A       172.217.2.110

;; Query time: 13 msec
;; SERVER: 192.168.0.12#65353(192.168.0.12)
;; WHEN: Thu Apr 19 00:32:44 EDT 2018
;; MSG SIZE  rcvd: 55
```

Voila!  A simple DNS proxy is up and running.

Setup Hosted Zone
-----------------

Now it's the meat of this experiment - setting up a hosted zone `.srv.qiu.home`.  We have a couple of options.  We can use the [file plugin](https://coredns.io/plugins/file/) that allows serving the zone from RFC 1035 style zone files.  Alternatively, we can setup an [etcd](coreos.com/etcd) cluster and use the [etcd plugin](https://coredns.io/plugins/file/) to read zone data from the etcd cluster.  I opted for the file plugin because I happen to have the zone files on hand when setting up bind9 (which also uses RFC 1035 zone file format) and setting up and maintaining an etcd cluster is probably a fight for another day.  I do like the promise of using an external data store for zone records though, since I don't have to manually update the zone files when a new host is available.


