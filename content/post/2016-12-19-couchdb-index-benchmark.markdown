+++
draft = true
date = "2016-12-19T23:34:56-05:00"
title = "CouchDB Indexing Benchmark"

+++

In the [last post](2016-11-16-couchdb-index-view-benchmark), we discussed how CouchDB's external query server works by examining the raw protocol. In this post, we're going to take a look at the performance of different query servers.

# The Setup

The benchmark is done on an AWS t2.large instance with CouchDB 1.6 running in a docker container. But since we're benchmarking python views as well, let's make a new docker image and add python query server to it. Here's the dockerfile:

    FROM couchdb
    RUN apt-get update -yqq && apt-get install -y python python-pip
    RUN pip install couchdb

Build a new image with that dockerfile, and start a couchdb instance with (assuming you named your image `couchdb-python` from the last step):

    docker run -p 9999:5984 -d -v $(pwd)/data:/usr/local/var/lib/couchdb couchdb-python 

Your couchdb instance will be accessible via `localhost:9999`. By default, the container is started in the admin party mode (everybody is an admin) but since we use it only for the purpose of testing, we won't bother with setting up username/password.

    $ curl http://localhost:9999/
    {"couchdb":"Welcome","uuid":"47a7b22e608a73fc2214ed13063923b8","version":"1.6.1","vendor":{"version":"1.6.1","name":"The Apache Software Foundation"}}

## Preparing the data

The data we're working have simple structures. We'll be generating data of the following form:

```json
{
    "metadata": {
        "docType": "userscore",
        "createdAt": "2016-12-19T19:28:14.000"
    },
    "username": "barry",
    "score": 912
}
```

Suppose we store username with their score in the document, whatever that is. It's a contrived example so bear with me :)

To populate a dataset for our benchmarking, let's use a script:

```python
import string
import sys
import requests
import random
import datetime
from multiprocessing import Pool


DB_URL = 'http://localhost:9999/test'


def random_name():
    generate_character = lambda _: random.choice(string.ascii_letters)
    return ''.join(map(generate_character, range(6)))


def random_date():
    # get a random date from within last year
    today = datetime.date.today()
    that_day = today - datetime.timedelta(days=random.randint(0, 366))
    return datetime.datetime.strftime(that_day, '%Y-%m-%d')


def generate_doc(_):
    doc = {
        'metadata': {
            'docType': 'score',
            'createdAt': random_date()
        },
        'username': random_name(),
        'score': random.randint(0, 5000)
    }
    response = requests.post(DB_URL, json=doc)
    response.raise_for_status()


if __name__ == '__main__':
    num_of_docs = int(sys.argv[1])
    requests.delete(DB_URL)  # delete the database if it exists already
    response = requests.put(DB_URL)     # create the test database
    print('Generating {} docs'.format(num_of_docs))
    pool = Pool(50)
    pool.map(generate_doc, range(num_of_docs))
    stats = requests.get('{}/'.format(DB_URL)).json()
    print('doc_count: {}'.format(stats['doc_count']))
    print('disk_size: {}'.format(stats['disk_size']))
```

You can seed the database by using: `python /path/to/script.py 100000` to create 100k documents. This is likely to take a while:

    python generate_data.py 100000
    doc_count: 100000
    disk_size: 111153301

As you can see, now we have a test database with 100000 documents.

## Setup Python Query Server

Python query server needs to be activated. You can either change it in the config file on the container and restart it or change it on the fly with the `_config` endpoint.

We can take a look at what's currently configured:

    $ curl http://localhost:9999/_config/query_servers
    {"javascript":"/usr/local/bin/couchjs /usr/local/share/couchdb/server/main.js","coffeescript":"/usr/local/bin/couchjs /usr/local/share/couchdb/server/main-coffee.js"}

Let's add python query server there:

    curl -XPUT -H"Content-Type: application/json" http://localhost:9999/_config/query_servers/python -d'"/usr/bin/python /usr/local/bin/couchpy"'

and verify that it's saved:

    $ curl http://localhost:9999/_config/query_servers
    {"javascript":"/usr/local/bin/couchjs /usr/local/share/couchdb/server/main.js","coffeescript":"/usr/local/bin/couchjs /usr/local/share/couchdb/server/main-coffee.js","python":"/usr/bin/python /usr/local/bin/couchpy"}

## Benchmark Javascript views

The view we are going to write is to calculate the total score of all users for a given month. We will have a map function to map each document to `([Year, Month], Score)` and a reduce function to sum up all the scores.

### Map/Reduce function

The map function written in Javascript:

```
function(doc) {
    if (doc.metadata && doc.metadata.createdAt) {
        var parts = doc.metadata.createdAt.split("-"),
            year = parts[0],
            month = parts[1];
        emit([year, month], doc.score);
    }
}
```

and the reduce function:

```
function(keys, values, rereduce) {
    return sum(values);
}
```

Let's save it as a design doc `_design/scoresByMonthJS:scoresByMonth`. You can use either Futon or curl or [cdbcli](https://github.com/kevinjqiu/cdbcli).

To invoke the view, we can send a curl request to `http://localhost:9999/test/_design/scoresByMonthJS/_view/scoresByMonth?limit=11&group=true`. However, keep in mind that whenever a view is invoked, the indexer will kick in and index any new changes since the last index. Because this is our first invocation of the view, it will index all changes (100K) so it's going to take some time. This will be the opportunity for us to observe the speed of indexing, so before we invoke that, let's get our script ready to monitor the speed of the indexing.

### Monitor changes-per-second metric

CouchDB exposes its indexing status through the `/_active_tasks` endpoint. It contains the number of changes to be indexed in total and the number of changes already indexed. From that, we can calculate the changes per second as our benchmark.

    python cps.py _design/scoresByMonthJS

This starts a monitoring script on the specified design doc, and prints out changes per second number every 1 second.

With this script running, in another terminal, let's trigger a view:

    curl "http://localhost:9999/test/_design/scoresByMonthJS/_view/scoresByMonth?limit=11&group=true"

Go back to the terminal where the monitoring script is run. We will see that it started to print out cps values:

    design doc: _design/scoresByMonthJS
    Press Ctrl+C to exit
    c/s = 3030.00
    c/s = 3636.00
    ...

And when the indexing is complete, press Ctrl+C and the average will be printed out:

    average = 3796.83

and in the other terminal, we will see the result:

    $ curl "http://localhost:9999/test/_design/scoresByMonthJS/_view/scoresByMonth?limit=11&group=true"

    {"rows":[
    {"key":["2015","12"],"value":8241946},
    {"key":["2016","01"],"value":20924965},
    {"key":["2016","02"],"value":19422002},
    {"key":["2016","03"],"value":21217217},
    {"key":["2016","04"],"value":20588868},
    {"key":["2016","05"],"value":21011332},
    {"key":["2016","06"],"value":20404601},
    {"key":["2016","07"],"value":20831013},
    {"key":["2016","08"],"value":21446896},
    {"key":["2016","09"],"value":20340594},
    {"key":["2016","10"],"value":20993863}
    ]}

So the average for a Javascript view is around 3796 changes per second.

### Native Reducer

Many of you with CouchDB knowledge will quick to point out that I used a Javascript function as reducer to calculate the sum of the values. This is not very efficient, since (1) data will have to be serialized and sent to the external query server to calculate the result and (2) Javascript isn't the fastest at mathematics (the default couchjs is using the Spider Monkey engine). We can cut short this loop by using the builtin `_sum` reducer, which is written in Erlang and run on the same runtime as CouchDB itself, therefore, cut the roundtrip to the query server plus the serialization/deserialization cost.

To use it, simply change the reducer function to `_sum`. Start the monitoring and trigger indexing.

    design doc: _design/scoresByMonthJS
    Press Ctrl+C to exit
    c/s = 6868.00
    c/s = 6969.00
    c/s = 6935.33
    c/s = 6842.75
    c/s = 6847.80
    c/s = 6817.50
    c/s = 7329.71
    c/s = 7234.12
    c/s = 7159.78
    c/s = 7100.30
    c/s = 7079.18
    c/s = 6510.62
    c/s = 6774.21
    ^Caverage = 6959.10

So, by simply changing the reducer from external to builtin, the indexing speed improved `183.3%`!

## Benchmark Python views

### Map/reduce
We save the following map/reduce function as `_design/scoresByMonthPY`:

Map:

    def map(doc):
        if 'metadata' in doc and 'createdAt' in doc['metadata']:
            created_at = doc['metadata']['createdAt']
            year, month, _ = created_at.split('-')
            yield [year, month], doc['score']

Reduce:

    def reduce(keys, values, rereduce):
        return sum(values)

We use a sub-optimal reducer to draw comparison with the first Javascript benchmark we did before. And it turned out that Python views are slightly more performant:

    $ python cps.py _design/scoresByMonthPY
    c/s = 5083.67
    c/s = 5024.75
    c/s = 5050.00
    c/s = 4999.50
    c/s = 4658.62
    c/s = 4702.11
    c/s = 4696.50
    c/s = 4710.27
    c/s = 4704.92
    c/s = 4566.64
    c/s = 4585.40
    c/s = 4601.81
    c/s = 4758.88
    c/s = 4646.00
    c/s = 4651.05
    average = 4762.68

Let's switch the reducer to CouchDB's builtin `_sum` function.

    design doc: _design/scoresByMonthPY
    Press Ctrl+C to exit
    c/s = 6363.00
    c/s = 6363.00
    c/s = 6329.33
    c/s = 6337.75
    c/s = 6282.20
    c/s = 6783.83
    c/s = 6680.43
    c/s = 6590.25
    c/s = 6508.89
    c/s = 6494.30
    c/s = 6211.50
    c/s = 6207.62
    c/s = 6225.93
    c/s = 6235.07
    average = 6400.94

The result isn't that different from Javascript map function with builtin reducer.

### Improving couchpy

