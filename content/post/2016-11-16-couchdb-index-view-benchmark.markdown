+++
title = "CouchDB Query Protocol and Index Benchmarking (Part 1)"
draft = false
date = "2016-11-16T00:05:38-05:00"
categories = ["couchdb"]
+++

Recently at `$DAYJOB` I had the opportunity to look deeper into how [CouchDB](https://couchdb.apache.org) indexing works and compared the performance of different indexers. Hopefully this series of articles will shed some light on how to get the most out of CouchDB's view indexing.

In this article we'll be going over the concept of CouchDB views and find out just how CouchDB indexes documents with the help of external query servers.

The version of CouchDB we will be using is 1.6.

# CouchDB views
CouchDB is a document-oriented database that's super easy to get started. You serialize your data into JSON, and throw it on the wire to CouchDB via an HTTP interface. To get the data out (querying) though, you will need to write "design docs" that contain map/reduce functions. Internally, CouchDB uses the map/reduce functions to build up a B+Tree index, so querying against that view is a simple tree lookup.

Out-of-the-box, CouchDB supports views written in JavaScript, however, support for other languages are available thanks to the CouchDB [query server protocol](http://docs.couchdb.org/en/1.6.1/query-server/protocol.html). CouchDB process itself does not do any querying. It simply loops through all the changes that have not been indexed since the last time, and send the changes to the external query server.

## MapReduce view updater

View indexing is triggered by the map-reduce view updater.

The following snippet is where it happens (`couch_mrview/src/couch_mrview_updater.erl`):

```erlang
map_docs(Parent, State0) ->                                                                                                                                                                   
    case couch_work_queue:dequeue(State0#mrst.doc_queue) of
        ...
        {ok, Dequeued} ->
            ...
            QServer = State1#mrst.qserver,
            DocFun = fun
                ...
                ({Id, Seq, Doc}, {SeqAcc, Results}) ->
                    {ok, Res} = couch_query_servers:map_doc_raw(QServer, Doc),
                    {erlang:max(Seq, SeqAcc), [{Id, Res} | Results]}
            end,
            ...
            couch_work_queue:queue(State1#mrst.write_queue, Results),
            map_docs(Parent, State1)
    end.
```

and `couch_query_servers:map_doc_raw` is encodes the document into JSON and sends it over to the external query server process:

```erlang
map_doc_raw(Proc, Doc) ->                                                                                                                                                                     
    Json = couch_doc:to_json_obj(Doc, []),
    {ok, proc_prompt_raw(Proc, [<<"map_doc">>, Json])}.

...
proc_prompt_raw(#proc{prompt_fun = {Mod, Func}} = Proc, Args) ->                                                                                                                              
    apply(Mod, Func, [Proc#proc.pid, Args]).
```

## External Query Server

The document is sent along with the action to be performed ([map_doc](http://docs.couchdb.org/en/1.6.1/query-server/protocol.html#map-doc)) to beh external query server process' stdin. Let's have a look at how an external query server is implemented. We'll take [couchpy](https://github.com/djc/couchdb-python/blob/master/couchdb/view.py#L182) as an example but it applies to any external query servers.

When a `map_docs` command is received via stdin of the couchpy process, the [following code](https://github.com/djc/couchdb-python/blob/master/couchdb/view.py#L75-L85) is being executed:

```python
def map_doc(doc):
    results = []
    for function in functions:
        try:
            results.append([[key, value] for key, value in function(doc)])
        except Exception as e:
            log.error('runtime error in map function: %s', e,
                      exc_info=True)
            results.append([])
            _log(traceback.format_exc())
    return results
```

Nothing too special here. The doc is passed to all `functions` inside the closure and the output of the function is gathered into a list to be returned. `functions` here is a variable available to the `map_doc` closure and is initialized by the [`add_lib`](http://docs.couchdb.org/en/1.6.1/query-server/protocol.html#add-fun) call, which is triggered when a view is being indexed.

```python
def add_fun(string):
    string = BOM_UTF8 + string.encode('utf-8')
    globals_ = {}
    try:
        util.pyexec(string, {'log': _log}, globals_)
    except Exception as e:
        return {'error': {
            'id': 'map_compilation_error',
            'reason': e.args[0]
        }}
    err = {'error': {
        'id': 'map_compilation_error',
        'reason': 'string must eval to a function '
                  '(ex: "def(doc): return 1")'
    }}
    if len(globals_) != 1:
        return err
    function = list(globals_.values())[0]
    if type(function) is not FunctionType:
        return err
    functions.append(function)
    return True
```

`util.pyexec` is a simple wrapper around the `exec` keyword in Python that turns code string into a function object:

```python
def pyexec(code, gns, lns):
    exec(code, gns, lns)
```

What this tells us is that **CouchDB's view functions inside the same design document get indexed together**. If you have a design document that contains multiple view functions that operate on different types of documents, this could negatively impact your performance. It's usually a good idea to have one view function per design document, unless the view functions have very strong cohesion.

# CouchDB Query Protocol in Practice
Now that we looked at how CouchDB invokes external query servers and how an external query server respond to certain protocol commands, let's put this into practice. We'd like to examine what's going on when a view is being indexed. We'll use couchpy again as an example.

First, let's create a couple of docs, each with a key "type" to indicate the type of documents:

```bash
$ curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "foo"}'
{"ok":true,"id":"db13c4d7dbf11110f1eadce071001e87","rev":"1-52308d7a89c9fb18c4c4e47d759834ed"}

$ curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "foo"}'
{"ok":true,"id":"db13c4d7dbf11110f1eadce071000f53","rev":"1-52308d7a89c9fb18c4c4e47d759834ed"}

$ curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "bar"}'
{"ok":true,"id":"db13c4d7dbf11110f1eadce07100189b","rev":"1-17ac4eb1776289a8d73ea6990401c56a"}
```

Then let's create a design doc that has a view function to map docs according to their types:

```python
def map(doc):
    yield doc.get('type', None), None
```

Save it as `_design/byType` and view name: `byType`.

To turn on couchpy logging, we can update CouchDB configuration via Futon. Go to http://localhost:5984/_utils/config.html and find key `python` the section `query_servers`, change the command to `/usr/local/bin/couchpy --debug --log-file=/tmp/couchpy.log`. Erlang config change does not require server reload, so this should take effect immediately.

Next, let's tail the log file:

```bash
log -F /tmp/couchpy.log
```

Now, trigger the view index by querying the view you have just created:

```bash
curl http://localhost:5984/test/_design/byType/_view/byType
```

You should be seeing in `/tmp/couchpy.log`:

```
[2016-12-05 23:52:31,380] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-05 23:52:31,381] [DEBUG] Returning  True
[2016-12-05 23:52:31,381] [DEBUG] Processing [u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None"]
[2016-12-05 23:52:31,381] [DEBUG] Returning  True
[2016-12-05 23:52:31,381] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-17ac4eb1776289a8d73ea6990401c56a', u'_id': u'db13c4d7dbf11110f1eadce071002ee1', u'type': u'bar'}]
[2016-12-05 23:52:31,381] [DEBUG] Returning  [[[u'bar', None]]]
[2016-12-05 23:52:31,382] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-52308d7a89c9fb18c4c4e47d759834ed', u'_id': u'db13c4d7dbf11110f1eadce071002546', u'type': u'foo'}]
[2016-12-05 23:52:31,382] [DEBUG] Returning  [[[u'foo', None]]]
[2016-12-05 23:52:31,382] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-52308d7a89c9fb18c4c4e47d759834ed', u'_id': u'db13c4d7dbf11110f1eadce071001e87', u'type': u'foo'}]
[2016-12-05 23:52:31,382] [DEBUG] Returning  [[[u'foo', None]]]
```

There we have it! CouchDB querying in action!

## reset

```
[u'reset', {u'timeout': 5000, u'reduce_limit': True}]
```

The first step is a [`reset` operation](http://docs.couchdb.org/en/1.6.1/query-server/protocol.html#reset) when the internal state of the query server is cleared. Couchpy simply clears the `functions` list:

```python
 def reset(config=None):
      del functions[:]
      return True
```

Couchpy seems to be ignoring the `timeout` and `reduce_limit` parameters passed in. Hrm...

## add_fun

```
[u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None"]
```

This is the next stage of indexing. CouchDB server sends the functions in the design doc to the query server. As we have seen earlier, couchpy calls Python's `exec` on the code, and save it as function objects internally.

## map_doc

```
[u'map_doc', {u'_rev': u'1-17ac4eb1776289a8d73ea6990401c56a', u'_id': u'db13c4d7dbf11110f1eadce071002ee1', u'type': u'bar'}]
```

After the internal state of the query server is setup, CouchDB will pass all eligible documents to the query server along with the operation `map_doc`. This will invoke all functions added via `add_fun` call in the query server's process on the document being passed.

The result of the function is collected into a list and returned to CouchDB via the processes' stdout.

# Index New Changes

## Adding a New Document
Now what happens if we add another document to the database?

Let's try it.

```
$ curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "bar"}'
{"ok":true,"id":"db13c4d7dbf11110f1eadce071003893","rev":"1-17ac4eb1776289a8d73ea6990401c56a"}
```

There we added a second `bar` document. Observe `/tmp/couchpy.log`. Nothing! That's right. Views in CouchDB 1.x **does not get indexed until the view is being queried**. If you're using CouchDB 1.x, it pays to have a cron job that periodically query all your views just to keep the views "warm", so your less-frequently used views are kept up to update and don't get hit with long indexing time when they do get queried.

Let's trigger query the view:

```
$ curl http://localhost:5984/test/_design/byType/_view/byType
{"total_rows":4,"offset":0,"rows":[
{"id":"db13c4d7dbf11110f1eadce071002ee1","key":"bar","value":null},
{"id":"db13c4d7dbf11110f1eadce071003893","key":"bar","value":null},
{"id":"db13c4d7dbf11110f1eadce071001e87","key":"foo","value":null},
{"id":"db13c4d7dbf11110f1eadce071002546","key":"foo","value":null}
]}
```

and now we get something in `couchpy.log` file:

```
[2016-12-06 00:49:22,327] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 00:49:22,327] [DEBUG] Returning  True
[2016-12-06 00:49:22,327] [DEBUG] Processing [u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None "]
[2016-12-06 00:49:22,328] [DEBUG] Returning  True
[2016-12-06 00:49:22,328] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-17ac4eb1776289a8d73ea6990401c56a', u'_id': u'db13c4d7dbf11110f1eadce071003893', u'type': u'bar'}]
[2016-12-06 00:49:22,328] [DEBUG] Returning  [[[u'bar', None]]]
```

As you can see, `reset` and `add_fun` are called again, because couchpy processes do not preserve their internal state once a view is finish indexing, and the `map_doc` operation is only called on the new document.

## Updating a Document

Let's now change one of the docs:

```
$ curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"_id": "db13c4d7dbf11110f1eadce071001e87", "_rev": "1-52308d7a89c9fb18c4c4e47d759834ed", "type": "quux"}'
{"ok":true,"id":"db13c4d7dbf11110f1eadce071001e87","rev":"2-2f95b6ed98722bf4a7d8750faa316313"}
```

and trigger view indexing. See what we've got in couchpy logs:

```
[2016-12-06 00:55:33,411] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 00:55:33,412] [DEBUG] Returning  True
[2016-12-06 00:55:33,412] [DEBUG] Processing [u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None "]
[2016-12-06 00:55:33,412] [DEBUG] Returning  True
[2016-12-06 00:55:33,412] [DEBUG] Processing [u'map_doc', {u'_rev': u'2-2f95b6ed98722bf4a7d8750faa316313', u'_id': u'db13c4d7dbf11110f1eadce071001e87', u'type': u'quux'}]
[2016-12-06 00:55:33,412] [DEBUG] Returning  [[[u'quux', None]]]
```

No surprises here. Couchpy only gets sent the new revision the doc was changed to. The query server does not need to know anything else.

## Deleting a Document

What about deletes? Now remember in CouchDB, deleting a document does not zero out the content, but rather, it creates a new revision of the document, marking it as "deleted".

```
$ curl -XDELETE http://localhost:5984/test/db13c4d7dbf11110f1eadce071001e87?rev=2-2f95b6ed98722bf4a7d8750faa316313
{"ok":true,"id":"db13c4d7dbf11110f1eadce071001e87","rev":"3-0dbaf84cadb9754e6619a10159852d4e"}
```

Documents marked as deleted won't be returned by any queries. Now let's have a look at how the query server respond to the request. Trigger the view query and observe `/tmp/couchpy.log` file.

```
[2016-12-06 01:01:59,143] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:01:59,144] [DEBUG] Returning  True
[2016-12-06 01:01:59,144] [DEBUG] Processing [u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None "]
[2016-12-06 01:01:59,144] [DEBUG] Returning  True
```

Nothing! That's right, even though the indexer was triggered, no other commands were sent to the query server. Deleted documents only get excluded from the final result, not from the view index file itself. To get rid of the deleted documents from the view, you will have to trigger a [view compaction](http://docs.couchdb.org/en/1.6.1/maintenance/compaction.html#views-compaction).

# Reduce

We have been ignoring one important functionality of CouchDB view so far - reduce functions. Reduce functions let you aggregate the mapped data. For example, if we want to sum up the number of docs per type, we will be providing the view a reduce function.

```python
def reduce(keys, values):
  return len(keys)
```

Here we're counting the number of keys. Save the reduce function into that view, trigger it with

```
$ curl http://localhost:5984/test/_design/byType/_view/byType?group=true
{"rows":[
{"key":"bar","value":2},
{"key":"foo","value":1}
]}
```

and observe the output in `couchpy.log`:

```
[2016-12-06 01:18:55,286] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:18:55,286] [DEBUG] Returning  True
[2016-12-06 01:18:55,286] [DEBUG] Processing [u'add_fun', u"def map(doc):\n  yield doc.get('type', None), None "]
[2016-12-06 01:18:55,286] [DEBUG] Returning  True
[2016-12-06 01:18:55,286] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-17ac4eb1776289a8d73ea6990401c56a', u'_id': u'db13c4d7dbf11110f1eadce071003893', u'type': u'bar'}]
[2016-12-06 01:18:55,286] [DEBUG] Returning  [[[u'bar', None]]]
[2016-12-06 01:18:55,287] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-17ac4eb1776289a8d73ea6990401c56a', u'_id': u'db13c4d7dbf11110f1eadce071002ee1', u'type': u'bar'}]
[2016-12-06 01:18:55,287] [DEBUG] Returning  [[[u'bar', None]]]
[2016-12-06 01:18:55,287] [DEBUG] Processing [u'map_doc', {u'_rev': u'1-52308d7a89c9fb18c4c4e47d759834ed', u'_id': u'db13c4d7dbf11110f1eadce071002546', u'type': u'foo'}]
[2016-12-06 01:18:55,287] [DEBUG] Returning  [[[u'foo', None]]]

[2016-12-06 01:31:51,135] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:31:51,135] [DEBUG] Returning  True
[2016-12-06 01:31:51,135] [DEBUG] Processing [u'reduce', [u'def reduce(keys, values):\n    return len(keys)'], [[[u'bar', u'db13c4d7dbf11110f1eadce071003893'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071002ee1'], None]]]
[2016-12-06 01:31:51,135] [DEBUG] Returning  [True, [2]]
[2016-12-06 01:31:51,136] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:31:51,137] [DEBUG] Returning  True
[2016-12-06 01:31:51,137] [DEBUG] Processing [u'reduce', [u'def reduce(keys, values):\n    return len(keys)'], [[[u'foo', u'db13c4d7dbf11110f1eadce071002546'], None]]]
[2016-12-06 01:31:51,137] [DEBUG] Returning  [True, [1]]
```

First you will notice is that since the design document is changed, all documents (changes) are reindexed. If you have a huge database, you may want to think twice before updating a design doc. Better yet, don't ever update the design document, but rather, migrate to a new design document (and finish indexing) and cut over to the new design document.

Then there are the `reduce` commands from CouchDB server to the query server. The reducer is sent with the result of the map function in the forms of `keys`, `values`. Since we don't emit any values, `values` will always be `None`.

Now our test database only contains 3 documents. Let's make it more interesting and add a lot more documents in.

Let's add 100 `bar` documents and 100 `foo` documents:

```bash
for x in {1..100}; do curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "bar"}'; done
for x in {1..100}; do curl -XPOST -H"Content-Type:application/json" http://localhost:5984/test -d'{"type": "foo"}'; done
```

Let's call the reducer:

```bash
$ curl http://localhost:5984/test/_design/byType/_view/byType?group=true
{"error":"os_process_error","reason":"{exit_status,1}"}
```

Hrmm... we got an error! Couchpy process crashed. Here's another complaint I have about CouchDB. View errors are very opaque. If you look at CouchDB logs, you will see a huge Erlang stack trace. Not much help there. However, the couchpy log does give us something useful. Maybe the query protocol can be amended to allow query servers to return more descriptive error message and having CouchDB relaying these error messages back to the user?

Anyhow, the error message we have in the couchpy log are:

```
[2016-12-06 01:34:59,213] [DEBUG] Processing [u'rereduce', [u'def reduce(keys, values):\n    return len(keys)'], [14, 18, 18, 18, 18, 18]]
[2016-12-06 01:34:59,214] [ERROR] Error: object of type 'NoneType' has no len()
Traceback (most recent call last):
  File "/usr/local/lib/python2.7/dist-packages/couchdb/view.py", line 146, in run
    retval = handlers[cmd[0]](*cmd[1:])
  File "/usr/local/lib/python2.7/dist-packages/couchdb/view.py", line 129, in rereduce
    return reduce(*cmd, **{'rereduce': True})
  File "/usr/local/lib/python2.7/dist-packages/couchdb/view.py", line 124, in reduce
    results = function(keys, vals)
  File "<string>", line 2, in reduce
TypeError: object of type 'NoneType' has no len()
```

Interesting! The operation that failed was actually [`rereduce`](http://docs.couchdb.org/en/1.6.1/query-server/protocol.html#rereduce). `Rereduce` is a CouchDB's optimization applied to divide-and-conquer large data sets. During `rereduce`, no `keys` are sent and only `values` are sent with `rereduce` flag set to `True`.

Let's modify our `reduce` function to take this into account.

```python
def reduce(keys, values, rereduce):
    if rereduce:
        return sum(values)
    return len(keys)
```

and trigger the view:

```
$ curl http://localhost:5984/test/_design/byType/_view/byType?group=true
{"rows":[
{"key":"bar","value":102},
{"key":"foo","value":101}
]}
```

That's it! And if we take a look at how CouchDB distributes documents to the reducer:

```
[2016-12-06 01:47:16,882] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:47:16,882] [DEBUG] Returning  True
[2016-12-06 01:47:16,882] [DEBUG] Processing [u'reduce', [u'def reduce(keys, values, rereduce):\n    if rereduce:\n        return sum(values)\n    return len(keys)'], [[[u'bar', u'db13c4d7dbf11110f1eadce07103bf77'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07103b6b2'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07103a903'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07103a06c'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071039212'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071038246'], None], [[u'bar', u'db13c4d7dbf11110f1eadce0710372d6'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071036338'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071035d9e'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071035735'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071035594'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071034722'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071033ef4'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071033105'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071032d0f'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071031f75'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071031b47'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100b399'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100a846'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100987c'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071009107'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071008240'], None], [[u'bar', u'db13c4d7dbf11110f1eadce0710080e9'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071007510'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071007295'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071007169'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071006178'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100600b'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100591f'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071004c04'], None], [[u'bar', u'db13c4d7dbf11110f1eadce07100425a'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071003aa3'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071003893'], None], [[u'bar', u'db13c4d7dbf11110f1eadce071002ee1'], None]]]
[2016-12-06 01:47:16,882] [DEBUG] Returning  [True, [34]]
[2016-12-06 01:47:16,883] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:47:16,883] [DEBUG] Returning  True
[2016-12-06 01:47:16,883] [DEBUG] Processing [u'rereduce', [u'def reduce(keys, values, rereduce):\n    if rereduce:\n        return sum(values)\n    return len(keys)'], [17, 17, 17, 17, 34]]
[2016-12-06 01:47:16,883] [DEBUG] Returning  [True, [102]]
[2016-12-06 01:47:16,884] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:47:16,884] [DEBUG] Returning  True
[2016-12-06 01:47:16,884] [DEBUG] Processing [u'reduce', [u'def reduce(keys, values, rereduce):\n    if rereduce:\n        return sum(values)\n    return len(keys)'], [[[u'foo', u'db13c4d7dbf11110f1eadce07106d438'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106ccf4'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106bec2'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106bcce'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106b7ec'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106b0d0'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106a6d4'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106a50b'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106a12e'], None], [[u'foo', u'db13c4d7dbf11110f1eadce0710692e5'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071068702'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071067f9c'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106780f'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071066912'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07106665a'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071065d4b'], None], [[u'foo', u'db13c4d7dbf11110f1eadce0710437d2'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071042cff'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071042b61'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071042375'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071041800'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07104172e'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071040aa1'], None], [[u'foo', u'db13c4d7dbf11110f1eadce0710404f1'], None], [[u'foo', u'db13c4d7dbf11110f1eadce0710402d4'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071040234'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103f423'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103e63a'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103d6c0'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103c7df'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103c6c0'], None], [[u'foo', u'db13c4d7dbf11110f1eadce07103c183'], None], [[u'foo', u'db13c4d7dbf11110f1eadce071002546'], None]]]
[2016-12-06 01:47:16,884] [DEBUG] Returning  [True, [33]]
[2016-12-06 01:47:16,885] [DEBUG] Processing [u'reset', {u'timeout': 5000, u'reduce_limit': True}]
[2016-12-06 01:47:16,885] [DEBUG] Returning  True
[2016-12-06 01:47:16,885] [DEBUG] Processing [u'rereduce', [u'def reduce(keys, values, rereduce):\n    if rereduce:\n        return sum(values)\n    return len(keys)'], [17, 17, 17, 17, 33]]
[2016-12-06 01:47:16,885] [DEBUG] Returning  [True, [101]]
```

Because we turned on the `group` flag, CouchDB will send the keys of the same group down to the reducer. When the reducer finishes and returns the results, CouchDB further sends the collected results to query server with the `rereduce` command to further aggregate the results.

For more information regarding `reduce` vs `rereduce`, see [the section](http://guide.couchdb.org/draft/views.html#reduce) from CouchDb: The Definitive Guide.

# Conclusion

The CouchDB query protocol is hauntingly simple. It uses JSON for inter-process communication and stdin/stdout as communication channel - very unixy and very easy to understand and to extend. For example, it wouldn't take too long for a seasoned programmer to write a Ruby query server to support Ruby views. However, it may not be the most efficient way to query the document store as we will find out in the next article.
