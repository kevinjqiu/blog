---
title: "Heartbeat-style Failure Detector using Gossip"
date: 2018-08-21T23:32:00-04:00
draft: false
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

As discussed, for simplicity reasons, we're just going to spin up a Flask API server with two endpoints: `GET /members` and `POST /members`.

* `GET /members` will simply return the node's membership list in JSON format:

```python
@app.route('/members', methods=['GET'])
def members():
    return flask.jsonify(membership_list.json())
```

* `POST /members` receives the membership list from another node and update the node's membership list using `MembershipList::update_all` method.

```
@app.route('/members', methods=['POST'])
def receive_heartbeat():
    request_json = flask.request.json
    membership_list.update_all(request_json)
    return flask.jsonify({})
```

And finally, we need a task runner that runs a scheduled task at every `protocol_period` (e.g., 1s).  The task will:

* increment its own heartbeat counter
* move the peers it hasn't had a heartbeat exceeding the threshold to "suspected" state
* remove the peers in suspected state which haven't had any heartbeats exceeding the threshold
* randomly pick two peers to send this node's membership list to

For the scheduler part, I just use the venerable [apscheduler](https://pypi.org/project/APScheduler/) package which is fairly easy to use:


```python
def tick():
    # self heartbeat
    membership_list.update_one(app.node_id,
                               lambda member_info: member_info.increment_heartbeat())

    membership_list.detect_suspected_nodes(app.suspicion_threshold_beats, app.protocol_period)
    membership_list.remove_dead_nodes(app.failure_threshold_beats, app.protocol_period)

    peers = membership_list.choose_peers(2, exclude=[app.node_id])
    for peer in peers:
        try:
            response = requests.post('http://{}/members'.format(peer), json=membership_list.json())
            logging.debug(response)
        except requests.exceptions.ConnectionError:
            pass
```

# Harness

So these are the main components of the failure detector.  The next step is to write some harness code to simulate a cluster with these nodes running.

For that, I use [pyinvoke](pyinvoke.org) which is a glorified Makefile.

These are the tasks I have:

* [`up`](https://github.com/kevinjqiu/failure_detector/blob/9d9d12ea8c389e1e4d19784af50c124d872e0a85/tasks.py#L90-L105) - bring up the cluster with 3 nodes having each other as peers.
* [`add-node`](https://github.com/kevinjqiu/failure_detector/blob/9d9d12ea8c389e1e4d19784af50c124d872e0a85/tasks.py#L123-L136) - start up a node and pick a random node in the cluster as its peer. The full membership list will eventually be gossipped to this node.
* [`list-members`](https://github.com/kevinjqiu/failure_detector/blob/9d9d12ea8c389e1e4d19784af50c124d872e0a85/tasks.py#L170-L180) - print out the membership list for every node in the cluster.
* [`kill`](https://github.com/kevinjqiu/failure_detector/blob/9d9d12ea8c389e1e4d19784af50c124d872e0a85/tasks.py#L51-L72) - kill a random node (or a specific node) in the cluster. This simulates a node failure.

# Demo

Now we can tie them together and do a demo of how heartbeat-style failure detection works.

## Start up a cluster of 5 nodes

    $ inv up --size 3
    Starting node: 127.0.1.1:36991 with peers 127.0.1.1:52326,127.0.1.1:36783
    Starting node: 127.0.1.1:52326 with peers 127.0.1.1:36991,127.0.1.1:36783
    Starting node: 127.0.1.1:36783 with peers 127.0.1.1:36991,127.0.1.1:52326

## Verify that these nodes know about each other

    inv list-members
    Node: 127.0.1.1:36991
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36991                31        1534962198  alive
    127.0.1.1:52326                31        1534962198  alive
    127.0.1.1:36783                31        1534962198  alive

    Node: 127.0.1.1:52326
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:52326                31        1534962198  alive
    127.0.1.1:36991                31        1534962198  alive
    127.0.1.1:36783                31        1534962198  alive

    Node: 127.0.1.1:36783
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36783                31        1534962198  alive
    127.0.1.1:36991                31        1534962198  alive
    127.0.1.1:52326                31        1534962198  alive

## Add a new node and show its members (initially it should only has itself and its initial peer)

    $ inv add-node && sleep 1 && inv list-members
    Starting node: 127.0.1.1:61586 with peers 127.0.1.1:36991

    ...

    Node: 127.0.1.1:61586
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:61586                 0        1534962309  alive
    127.0.1.1:36991                 0        1534962309  alive

## After a while, that node's presence is gossipped to all the nodes

    $ inv list-members
    Node: 127.0.1.1:36991
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36991               210        1534962377  alive
    127.0.1.1:52326               209        1534962377  alive
    127.0.1.1:36783               209        1534962376  alive
    127.0.1.1:61586                68        1534962377  alive

    Node: 127.0.1.1:52326
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:52326               210        1534962377  alive
    127.0.1.1:36991               210        1534962377  alive
    127.0.1.1:36783               210        1534962377  alive
    127.0.1.1:61586                68        1534962377  alive

    Node: 127.0.1.1:36783
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36783               210        1534962377  alive
    127.0.1.1:36991               210        1534962377  alive
    127.0.1.1:52326               209        1534962376  alive
    127.0.1.1:61586                68        1534962377  alive

    Node: 127.0.1.1:61586
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:61586                68        1534962377  alive
    127.0.1.1:36991               210        1534962377  alive
    127.0.1.1:52326               210        1534962377  alive
    127.0.1.1:36783               210        1534962377  alive

## Kill a random node, and watch it disappear from the membership list of other nodes

The best way to do this is to have a terminal (or tmux panel) running `watch inv list-members` while run `inv kill` in another.

    $ inv kill
    Kill peer {'bind': '127.0.1.1:61586', 'pid': 21969}

And observe in the other window:

    Node: 127.0.1.1:36991
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  ---------
    127.0.1.1:36991               557        1534962724  alive
    127.0.1.1:52326               557        1534962724  alive
    127.0.1.1:36783               557        1534962724  alive
    127.0.1.1:61586               407        1534962716  suspected

    Node: 127.0.1.1:52326
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  ---------
    127.0.1.1:52326               557        1534962724  alive
    127.0.1.1:36991               557        1534962724  alive
    127.0.1.1:36783               555        1534962722  alive
    127.0.1.1:61586               407        1534962716  suspected

    Node: 127.0.1.1:36783
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  ---------
    127.0.1.1:36783               557        1534962724  alive
    127.0.1.1:36991               556        1534962723  alive
    127.0.1.1:52326               557        1534962724  alive
    127.0.1.1:61586               407        1534962716  suspected

    Node: 127.0.1.1:61586
    ================================================================
    Node is down

Notice the "suspected" status for the newly killed node.  After a while:

    Node: 127.0.1.1:36991
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36991               638        1534962805  alive
    127.0.1.1:52326               638        1534962805  alive
    127.0.1.1:36783               638        1534962805  alive

    Node: 127.0.1.1:52326
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:52326               638        1534962805  alive
    127.0.1.1:36991               638        1534962805  alive
    127.0.1.1:36783               638        1534962805  alive

    Node: 127.0.1.1:36783
    ================================================================
    id                 last_heartbeat    last_timestamp  status
    ---------------  ----------------  ----------------  --------
    127.0.1.1:36783               638        1534962805  alive
    127.0.1.1:36991               638        1534962805  alive
    127.0.1.1:52326               638        1534962805  alive

    Node: 127.0.1.1:61586
    ================================================================
    Node is down

The node `127.0.0.1:61586` is completely removed from the membership list of other nodes.


I hope this demonstrates the aspects of a simple failure detector with gossip.  It certainly solidified my understanding of such topic while having fun building it :)
