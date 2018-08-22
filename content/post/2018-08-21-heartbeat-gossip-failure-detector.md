---
title: "Heartbeat-style Failure Detector using Gossip"
date: 2018-08-21T23:32:00-04:00
draft: true
---

I recently started part-time Master's degree at University of Illinois Urbana-Champaign.  It has been on my bucket list for a long time, and I finally got the chance to do it.

One of the courses I'm taking this semester is [distributed systems](https://www.coursera.org/learn/cloud-computing).  In my day job, I come in contact a lot with distributed systems, and this course so far has helped me tremendously in understanding a lot of the basic concepts of them.  One of such concepts is failure detection and how to multicast messages across the network using gossip.  To enhance my understandings of such top, I figured I could write a simple failure detector using these concepts.

*Disclaimer*: The code example here is purely educational, so don't use it anywhere near a production system.  Also, feel free to contact me regarding any bugs or errors in understanding.

# Components
## Membership

In a distributed system composed of a cluster of nodes/processes, how does one node/process know its peers in the cluster?  One way to do it is to maintain a static membership list and keep a copy of it for every node in the cluster, but then how do we disseminate such information to new nodes joining the cluster?  Also, in a distributed system, failure is the norm rather than the exception, so when a node fails, how do other nodes detect failure and remove it from its membership list?

## Multicast

Multicast is the way in which we disseminate data in a distributed system.  We could use it to multicast the membership list to the nodes in the cluster so nodes in the cluster will have an eventually consistent membership list on each node.

There are many multicast methods, but the [gossip protocol](https://en.wikipedia.org/wiki/Gossip_protocol) is the one we're going to implement here, which is fairly simple to conceptualize and fairly efficient.

On the high level, the protocol works as follows:

For each *protocol period*:
- Every node picks `m` (usually 2) of its immediate neighbours and send message to them
- The `m` nodes receiving the message in turn pick `m` of their immediate neighbours and send the message to them

Given a cluster of `N` nodes, gossip takes on the order of `log(N)` protocol periods to finish disseminate message to all nodes in the cluster.

## Heartbeat-style Failure Detection

Heartbeating is one of the mechanisms for detecting failures in a distributed system.  For every protocol period, a node `P` increments its own heartbeat counter, and send the counter to neighbouring nodes `Q` using multicast (e.g., gossip).  If `Q` does not receive a heartbeat from `P` for a given amount of time (or missed beats), `Q` will remove `P` from its own membership list.

### False positive and Suspicion

Sometimes, network failures happen and the heartbeat message from `P` to `Q` may not be delivered in time.  If `Q` removes `P` right away, this may lead to false positives.  To reduce the probability, a "suspicion" mechanism is used so if `P` misses a couple of heartbeats, it will first be moved to a "suspected" state, and if `Q` still hasn't heard from `P` for a given time period, `Q` will then remove `P` from its membership list.

So these are the basics of our heartbeat-style failure detector with gossip.  Let's look at how we can implement it.

# Scope of Implementation

First, I want to spell out the scope of this toy failure detector.

## Transport: HTTP

Yes, I know using TCP for heartbeat isn't the most efficient, but for the purpose of this simulation, I'm just going to use Python+Flask to quickly build up an API server over HTTP.  Socket programming isn't the focus of this simulation.

## Message Format: JSON

Again, yes, JSON is heavyweight for heartbeating, but it's relatively human-friendly and it allows you to use the familiar tooling to interact with the server (e.g., `curl` and python-requests)

## Network environment: 127.0.0.1/8

Yes, I'm simulating on the loopback interface, with each process having a different port (and possibly different IP addresses in the `/8` network).  The implementation should work for processes on different machines/networks as long as they're routable.

# Goal of simulation

The goal of the simulation is to be able to show:

* each node maintaining a membership list that's eventually consistent
* when a new node joins the cluster, it will eventually have the same membership list as everybody else
* when a node is killed, the failure is detected, and the failed node is eventually removed from the membership list

# Implementation

note: The complete code is in this [repository](https://github.com/kevinjqiu/failure_detector).

First, we need a data structure to store membership information for a specific member:

```python
class MemberInfo:
    def __init__(self, id, last_heartbeat, last_timestamp):
        self.id = id                           # id is in the form of <ip>:<port>
        self.last_heartbeat = last_heartbeat   # last received heartbeat sequence no.
        self.last_timestamp = last_timestamp   # last heartbeat received timestamp
        self.status = 'alive'
        self._lock = threading.RLock()

    def increment_heartbeat(self):
        with self._lock:
            self.last_heartbeat += 1
            self.last_timestamp = int(time.time())

    def update(self, updated_member_info):
        with self._lock:
            if updated_member_info.last_timestamp <= self.last_timestamp:
                return
            if updated_member_info.last_heartbeat <= self.last_heartbeat:
                return
            self.last_heartbeat = updated_member_info.last_heartbeat
            self.last_timestamp = int(time.time())
            self.status = 'alive'

    def set_status(self, status):
        with self._lock:
            self.status = status
```

It's a simple Python class to store `id`, `last_heartbeat`, `last_timestamp` and the `status`.  It uses a reentrant lock to synchronize access to the attributes on object.
The `MemberInfo` class has a few methods to update its attributes in a thread-safe way.

We also need a data structure to represent a membership list:
```python
class MembershipList:
    def __init__(self):
        self._members = {}  # Type: MemberInfo
        self._lock = threading.RLock()

    ...

    def json(self):
        """Returns the JSON representation of the membership list"""
        ...

    def update_all(self, membership_list):
        with self._lock:
            for member_to_update in membership_list:
                member_info = MemberInfo(
                    member_to_update['id'],
                    member_to_update['last_heartbeat'],
                    member_to_update['last_timestamp'],
                )
                if not member_to_update['id'] in self._members:
                    self._members[member_to_update['id']] = member_info
                else:
                    existing_member = self._members[member_to_update['id']]
                    existing_member.update(member_info)
```

The important method here is `update_all`, where an incoming membership list from another node needs to be "merged" with the membership list of the current node.
