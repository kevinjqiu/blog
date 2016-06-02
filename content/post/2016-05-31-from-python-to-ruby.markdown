+++
date = "2016-05-31T23:04:13-04:00"
title = "Ruby for Pythonistas"

+++

It's been 11 years since I first encountered Python, and it's been my favourite programming language ever since. However, I've always been curious about the Ruby language. On the surface, they have a lot in common: both dynamic, object-oriented, interpreted, vm-based, and optimize for developer happiness rather than machine speed. However, they have quite different data models, syntax and community culture.

This post is a summary of my journey learning Ruby as a seasoned Python developer, and my thoughts comparing these two popular languages.

Disclaimer:

* I'm by no means a Ruby expert. My understand of Ruby so far has been quite superficial.
* Most of the points here are my notes while going through the excellent [Ruby Koan](http://rubykoans.com/) exercises. A big shout out to them!

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

Hashes
======

Ruby hashes are equivalent of Python dictionaries. They can be constructed and accessed using similar syntax.

No `KeyError`
-------------

In Python, when accessing a key that doesn't exist in the dictionary, you get a `KeyError`:

    >>> x={'a': 1}
    >>> x['b']
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      KeyError: 'b'

In Ruby, you simply get `nil`:

    irb(main):038:0> a={:a => 1, :b => 2}
    => {:a=>1, :b=>2}
    irb(main):039:0> a[:c]
    => nil

However, doing a `fetch` will result in `KeyError` if it doesn't exist:

    irb(main):040:0> a.fetch(:c)
    KeyError: key not found: :c
        from (irb):40:in `fetch'
        from (irb):40
        from /usr/bin/irb:11:in `<main>'

Default value
-------------

In Ruby, default value functionality is built-in with `Hash` class:

    irb(main):041:0> x=Hash.new([])
    => {}
    irb(main):042:0> x[:one]
    => []

In Python, we use `collections.defaultdict`:

    >>> import collections
    >>> x=collections.defaultdict(list)
    >>> x["one"]
    []

Python's `defaultdict` is more flexible, allowing the default value be obtained via a callable. Maybe there's a way to achieve the same thing with Ruby but I haven't found it.

Gotcha: The default value in Ruby's `Hash` though is shared among all instances:

    irb(main):043:0> x=Hash.new([])
    => {}
    irb(main):044:0> x[:one] << "1"
    => ["1"]
    irb(main):045:0> x[:two] << "2"
    => ["1", "2"]
    irb(main):046:0> x[:two]
    => ["1", "2"]

This could lead to subtle bugs if not careful.

A safer approach is to use block initialization:

    irb(main):047:0> x=Hash.new { |hash, key| hash[key] = [] }
    => {}
    irb(main):048:0> x[:one] << 1
    => [1]
    irb(main):049:0> x[:two] << 2
    => [2]
    irb(main):050:0> x[:two]
    => [2]

[Block](http://rubylearning.com/satishtalim/ruby_blocks.html) is one of my favourite Ruby language features.


Strings
=======

Strings are similar in both languages, except Ruby strings are mutable, while Pythons' are immutable. Ruby also has more ways to escape quotes:

    irb(main):051:0> %(I can use ' and " here no problem)
    => "I can use ' and \" here no problem"

    irb(main):052:0> %!and here '"!
    => "and here '\""

    irb(main):053:0> %{or here '"}
    => "or here '\""

    irb(main):054:0> %{multi
    irb(main):055:0" line
    irb(main):056:0" strings%}
    => "multi\nline\nstrings%"

You can use regex as string index to extract the matched substring:

    irb(main):065:0> "j'ai 34 ans"[/\d+/]
    => "34"

Symbols
=======

Symbols are a unique in Ruby that's not present in Python (although I wish). It has permeated into the design of other modern languages, like Clojure and Elixir. You can think of symbols as a way to do free-form enums, a way to name something, as oppose to just some free form texts.

You can get all symbols in the current scope:

    irb(main):060:0> Symbol.all_symbols
    [... long list of global symbols ...]

You can use symbols to refer to functions:

    irb(main):062:0> ''.respond_to? :to_i
    => true

You can dynamically create a symbol from strings:

    irb(main):063:0> 'abc'.to_sym
    => :abc

Methods
=======

Default values
--------------

Same as Python:

    def foo(a, b='default') 

Variadic arguments
------------------

Same as Python:

    def foo(a, *c)

Inside the method, `c` is available as an `Array`.

Invocation and Return
---------------------

Ruby method invocation does not require parentheses, unless it's it results in ambiguity. e.g., you can omit parens in:

    def foo(arg)
      ...
    end

    foo :bar

but you have to use parens to disambiguate in situations like:

    def foo(arg)
    end

    def bar(arg)
    end

    bar(foo arg)

In Python, parens are mandatory.

In Ruby, almost everything is an expression. In the case of a method definition, the last expression becomes the return value of the method. Some people call it implicit returns, and people have mixed feelings about it. Personally I like the everything-is-an-expression model and using the last expression as the return value feels natural. In Python, you have to use `return`, otherwise, it implicitly returns `None`.

Keyword arguments
-----------------

Ruby 1.x doesn't have keyword arguments as a language feature. This is a little disappointing. However, it's idiomatic in Ruby to have a method accept a hash, and use symbols to simulate keyword arguments:

    irb(main):068:0> def foo(args)
    irb(main):069:1>   puts args
    irb(main):070:1> end
    => :foo
    irb(main):071:0> foo(a: 5, b: 6)
    {:a=>5, :b=>6}

Since you can omit `{}` in Hash construction, this code is almost like Python's keyword arguments. However, you have to do argument validation yourself.

In Ruby 2.x, this pattern has been elevated as a language feature, so now Ruby has proper keyword argument support. However, I have not seen an equivalent of Python's [keyword-only argument](https://www.python.org/dev/peps/pep-3102/) feature.


Constants
=========

Ruby symbols start with capital letters are "constants", so classes are also "constants":

    irb(main):074:0> class foo
    irb(main):075:1> end
    SyntaxError: (irb):74: class/module name must be CONSTANT
            from /usr/bin/irb:11:in `<main>'

Ruby constants are more enforced than their counterpart in Python. (well, technically, Python doesn't have constants, only by convention, all cap symbols are considered constants.)

    irb(main):076:0> A=1
    => 1
    irb(main):077:0> A=2
    (irb):77: warning: already initialized constant A
    (irb):76: warning: previous definition of A was here
    => 2

Truthiness
==========

Truthiness in Ruby is a lot different from Python. Python has the concept of "falsy", in which `0`, `[]`, `{}`, `''` are all evaluated to `False`. In Ruby, however, only `false` is false, and everything else is treated as `true`:

    def is_true?(value)
      if value
        :true
      else
        :false
      end
    end

    irb(main):098:0> is_true? 0
    => :true
    irb(main):099:0> is_true? '0'
    => :true
    irb(main):100:0> is_true? ''
    => :true
    irb(main):101:0> is_true? []
    => :true
    irb(main):103:0> is_true?({})
    => :true
    irb(main):104:0> is_true?(false)
    => :false

Exceptions
==========

Ruby's exception hierarchy is a lot like Python's, at least in name:

    RuntimeError < StandardError < Exception

To handle exceptions, you use `begin...rescue...ensure` rather than `try...except...finally`.

Map/Reduce/Filter
=================

Ruby the language itself is not a functional language, although it provides machinery for you to program in a functional way, such as using high-order functions.

When first learning Ruby, I was looking for my familiar friends `map`/`reduce`/`filter` but couldn't find any. Then I realized they're called something completely different:

In Ruby, `filter` is achieved using `select`/`find_all`:

    irb(main):105:0> [1,2,3,4,5].select { |x| x % 2 == 0 }
    => [2, 4]
    irb(main):106:0> [1,2,3,4,5].find_all { |x| x % 2 == 0 }
    => [2, 4]

`map` is equivalent to `collect`/`map`:

    irb(main):107:0> [1,2,3,4,5].collect { |x| x * 2 }
    => [2, 4, 6, 8, 10]

`reduce` is not `reduce`, nor is it called `fold`, but is weirdly named `inject`:

    irb(main):108:0> [1,2,3,4,5].inject(0) { |x, y| x + y }
    => 15

Blocks
======

As I eluded to before, blocks are one of my favourite Ruby language features. It's comparable to Python's [context managers](https://docs.python.org/2/reference/compound_stmts.html#with), but it can be invoked without using a keyword and can be added to any method calls. It feels more natural.

Similar to Python (using `contextlib.contextmanager`), you can invoke a block by `yield` to the caller:

    def do_with_logging
        log "start"
        yield
        log "end"
    end

    do_with_logging {
        # serious business
    }

A Ruby method is also able to determine if it's called with a block being passed by using `block_given?` method.

    def do_it
        if block_given?
            yield
        else
            put "no block"
        end
    end

Classes
=======

Ruby classes are defined in a similar way as Python.

self
----

Ruby's `self` can reference different things in different scopes. For example, inside a class definition, `self` refers to the class object (kind of like when you define a `classmethod` in Python), but inside an instance method, `self` refers to the instance of the class.

private
-------

Python doesn't have `private` members or methods. With Ruby however, you *can* define "private" methods if you put `private` in front of your method definition.

    class Foo
        private def foo
            puts "private"
        end
    end

Outside callers can't call `foo`. Members of the same class can call `foo` if only it is called with `self` being the implicit receiver:

    class Foo
        private ...

        def use_foo
            foo  # this is fine
            self.foo  # Not allowed
        end
    end

Ruby's instance variables are private with `@` prefix:

    class Foo
        def initialize(name)
            @name = name
        end
    end

To access `@name` you can define getters and/or settings:

    class Foo
        attr_accessor :name
        # or attr_reader :name to make it readonly
        ...
    end

Although the `private` restriction can be circumvented by metaprogramming:

    foo = Foo.new
    foo.instance_variable_get("@name")

Overall, I think Ruby encourages more encapsulation and better design.

Define class methods
--------------------

You can refer to the class by name when defining methods to make class methods:

    class Foo
        def Foo.bar
        end
    end

Alternatively, remember we said before that `self` inside a class definition refers to the class itself? So this works too:

    class Foo
        def self.bar
        end
    end

Another way to write class method uses an inner class:

    class Foo
        class << self
            def bar
            end
        end
    end

This is good if you want to group class methods together.

Open class
----------

A powerful (yet controversial) feature of Ruby is that you can "amend" any Ruby classes (even the builtin ones) during runtime. It's like monkey-patching on steroids.

    class ::Integer
        def even?
            self % 2 == 0
        end
    end

Now suddenly `2.even?` is a thing. It certainly makes writing your own DSL a lot easier, but it may lead to magical code that's hard to track down.

Inheritance
-----------

Ruby uses `A < B` to mean class `A` inherits from class `B`. `super` is available to refer to the same-named methods in the super class. Because Ruby is single inheritance, there's no ambiguity of `super` here.

Mixin
-----

Ruby's class can only have a single parent, but you can "mixin" behaviour into your class by `include` other modules. Compared to Python, which does support multiple inheritance, and extra attention has to be paid to avoid diamond inheritance problem.

I feel the Ruby design is more thought-out. As oppose to give more ropes to developers to hang themselves, it makes the use case of multiple inheritance more clear (only for mixins).


Message Passing
===============

Ruby's object-oriented model is based on the idea of message passing. As opposed to invoking using `obj.method`, you can pass a message `method` to object `obj`:

    obj.send :method

    obj.__send__ :method

Use `respond_to?` to test if a receiver can handle such message:

    if obj.respond_to? :method
        ...
    end

`obj` can implement `method_mssing?` method to implement generic method dispatcher. With Python, you can achieve the same thing with `__getattribute__` magic method.
