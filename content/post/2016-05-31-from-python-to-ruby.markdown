+++
date = "2016-05-31T23:04:13-04:00"
draft = true
title = "Ruby for Pythonistas"

+++

It's been 11 years since I first encountered Python, and it's been my favourite programming language ever since. However, I've always been curious about the Ruby language. On the surface, they have a lot in common: both dynamic, object-oriented, interpreted, vm-based, and optimize for developer happiness rather than machine speed. However, they have quite different data models, syntax and community culture.

This post is a summary of my journey learning Ruby as a seasoned Python developer, and my thoughts comparing these two popular languages.

Nil
===

Ruby `nil` is Python `None` is `null` in other languages. However, it's different in the sense that it's an instance of the `nil::Nil` class.

object
======

Objects have ids, just like Python.

```ruby
''.object_id
```

in Python:

```python
id('')
```

Arrays
======

In my opinion, Ruby arrays are a lot richer than Python lists.

Concatenation
-------------

Use the `<<` operator on arrays: 

```ruby
a << 3
```

in Python:

```python
a.append(3)
```

Access
------

To access an array, you can use the array index just like it is in almost every other language. However, Ruby's `Array` class also implements convenient methods to access the first and last element of the array:

    irb(main):004:0> a = [1, 2, :three]
    => [1, 2, :three]
    irb(main):005:0> a[0]
    => 1
    irb(main):006:0> a[-1]
    => :three
    irb(main):007:0> a.last
    => :three
    irb(main):008:0> a.first
    => 1

Slices and Ranges
-----------------

Both Python and Ruby support slicing although the syntax are slightly different:

Ruby: `arr[a, b]`, where `a` is the starting index and `b` is the size of the slice.

    irb(main):012:0> a=[:one, :two, :three]
    => [:one, :two, :three]
    irb(main):013:0> a[0,1]
    => [:one]

Python: `arr[a:b]`, where `a` is the starting index and `b` is the ending index (exclusive)

    >>> a=[1,2,3]
    >>> a[0:1]
    [1]

Python has `range` and `xrange` builtin functions.

    >>> list(range(10))
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

Ruby also has range, but it provides language construct for `Range` objects:

    irb(main):010:0> (1..5).to_a
    => [1, 2, 3, 4, 5]

    irb(main):011:0> (1...5).to_a
    => [1, 2, 3, 4]

It's worth noting that double dot (`..`) creates an inclusive interval whereas triple dot (`...`) creates an exclusive interval. This threw me off at first, since somehow my brain associate `...` with inclusive and `..` being exclusive.

In Ruby, you can also pass a range object to an array, and that behaves more or less the same way as Python's slicing:

    irb(main):019:0> a[1...3]
    => [:two, :three]

Python's slicing is also pretty flexible. Python's special method `__getitem__` is able to take a range object (or any object for that matter) and override the behaviour of `[]` operator.

Unpacking
---------

One of the nice features of Python is list/tuple unpacking, e.g.,

    >>> a=['one', 'two']
    >>> one, two = a
    >>> one
    'one'
    >>> two
    'two'
    >>>

IMO, Ruby does it better. 

    irb(main):020:0> a=[:one, :two]
    => [:one, :two]
    irb(main):021:0> one, two = a
    => [:one, :two]
    irb(main):022:0> one
    => :one
    irb(main):023:0> two
    => :two

Left side doesn't have to match the right side cardinally:

    irb(main):024:0> one, two = [1, 2, 3, 4, 5]
    => [1, 2, 3, 4, 5]
    irb(main):025:0> one
    => 1
    irb(main):026:0> two
    => 2

    irb(main):027:0> one, two = [1]
    => [1]
    irb(main):029:0> one
    => 1
    irb(main):030:0> two
    => nil

In Python, that's a `ValueError`:

    >>> one, two = [1,2,3,4,5]
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      ValueError: too many values to unpack (expected 2)

    >>> one, two = [1]
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      ValueError: not enough values to unpack (expected 2, got 1)


Ruby also supports "wildcard" match which in Python-land is only available after Python 3.

    irb(main):031:0> first, *rest = [1,2,3,4,5]
    => [1, 2, 3, 4, 5]
    irb(main):032:0> first
    => 1
    irb(main):033:0> rest
    => [2, 3, 4, 5]

Both Languages support inline swapping:

    irb(main):034:0> a, b = [1, 3]
    => [1, 3]
    irb(main):035:0> a, b = b, a
    => [3, 1]
    irb(main):036:0> a
    => 3
    irb(main):037:0> b
    => 1

