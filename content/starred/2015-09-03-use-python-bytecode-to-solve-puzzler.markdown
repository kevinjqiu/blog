+++
layout = "post"
title = "Use Python bytecode to solve puzzler"
date = "2015-09-03 22:16:36 -0400"
comments = "true"
categories = ["python"]
+++

## Learning Python Internals

Recently I stumbled upon [this wonderful set of videos on Python interpreter internals](https://www.youtube.com/playlist?list=PLwyG5wA5gIzgTFj5KgJJ15lxq5Cv6lo_0). (Thanks to [Philip Guo](http://pgbovine.net/) for creating them and thanks to Michael Kennedy (@mkennedy) and his [Talk Python to me](http://talkpython.fm/) show that brought this on my radar)

I've been using Python for about ten years but I've never really truly been able to understand how the interpreter works, nor was I familiar with the Python virtual machine or the bytecode. These videos may just be the extra help I needed to get me started at the internals of Python.

So far, I've only watched 2 lectures and I'm already learning a lot. I learned where to find a list of opcodes in the source code, where the main eval loop is, and what internal states the Python virtual machine keeps.

Then I thought to myself, why not use this new found power to solve some Python mysterious that have been puzzling me?

## The puzzler

A few days ago, one of my former co-workers posted this puzzler:

```python
(a, b) = a[b] = {}, 5
```

What are the values of `a` and `b` after the assignment? Well, it's not obvious what the order of assignment it is going to be. Putting it in the REPL gives us this:

```
>>> (a, b) = a[b] = {}, 5
>>> a
{5: ({...}, 5)}
>>> a[5]
({5: ({...}, 5)}, 5)
>>> a[5][0]
{5: ({...}, 5)}
>>> a[5][0][5]
({5: ({...}, 5)}, 5)
```

OK, so there appears to be a circular reference going on here. The object that `a` refers to has an element that refers to the object that `a` refers to and so on and so forth. Now, the question is, how did the circular reference get there?

Well, all Python source code eventually get compiled down to bytecode and executed on the virtual machine. In order to understand what that line actually does, we need to look at the byte code.

It turns out that Python comes with a module to disassemble source code into byte codes (assembly for the virtual machine):

```
$ python -m dis
a, b = a[5] = {}, 5
^D
  1           0 BUILD_MAP                0
              3 LOAD_CONST               0 (5)
              6 BUILD_TUPLE              2
              9 DUP_TOP
             10 UNPACK_SEQUENCE          2
             13 STORE_NAME               0 (a)
             16 STORE_NAME               1 (b)
             19 LOAD_NAME                0 (a)
             22 LOAD_CONST               0 (5)
             25 STORE_SUBSCR
             26 LOAD_CONST               1 (None)
             29 RETURN_VALUE
```

Alright, so that humble little line of code is actually 12 instructions for the Python virtual machine. Each instruction manipulates the virtual machine's internal state in some way. CPython is a stack-based interpreter, which means certain instructions puts values on the stack and other instructions consume them from the stack.

Let's go through the instructions:

```
0 BUILD_MAP                0
```

First off, it tells the interpreter to make a map object and put it on the value stack. After this instruction, our value stack looks like this:

```
+----+
| {} |
+----+
```

Next up:

```
3 LOAD_CONST               0 (5)
```

This loads a constant (`5`) on the stack.
```
+----+
| {} |
+----+
| 5  |
+----+
```

Next:

```
6 BUILD_TUPLE              2
```
This instruction builds a `PyTuple` object of size `2`, which is in the argument of the opcode. It consumes the top `2` things on the stack and make a 2-tuple using these values and put the result tuple on the value stack:

```
+---------+
| ({}, 5) |
+---------+
```

```
9 DUP_TOP
```
Next we have the `DUP_TOP` instruction. It probably stands for "duplicate the top of the stack", and reading the corresponding code in the eval loop, this seems to be what it's doing: it gets the object from the top of the stack without popping it off and push the value on the stack, while incrementing the refcount of the object.

It's worth noting that this only duplicates the tuple object. The elements inside the tuple are of type `*PyObject`, which are pointers to the corresponding values (the dict and the integer), and are not duplicated by this instruction. Here's the value stack after this instruction:

```
+---------+
| ({}, 5) |
+---------+
| ({}, 5) |
+---------+
```

```
10 UNPACK_SEQUENCE          2
```
The next instruction is `UNPACK_SEQUENCE` with argument `2`. This will first pop the stack, so `({}, 5)` is off the stack, and then push each element from the tuple on the stack in reverse order. After this instruction, the stack will be:

```
+---------+
| ({}, 5) |
+---------+
|   5     |
+---------+
|   {}    |
+---------+
```

```
13 STORE_NAME               0 (a)
16 STORE_NAME               1 (b)
```

The next two instructions deal with "names", which are variables for the scope of the frame. `STORE_NAME a` will pop the stack, and point `a` to the value, and similarily for `STORE_NAME b`. After this instruction, there will be two bindings in the frame: `a` and `b` and the stack will be back to having only one element, the tuple:

```
stack:
+---------+
| ({}, 5) |
+---------+

bindings:
a <- {}
b <- 5
```

The next two instructions:
```
19 LOAD_NAME                0 (a)
22 LOAD_CONST               0 (5)
```

`LOAD_NAME a` will push the value that the variable is bound to on the stack, so:

```
stack:
+---------+
| ({}, 5) |
+---------+
|    {}   |
+---------+

bindings:
a <- {}
b <- 5
```

and `LOAD_CONST 5`, as we've seen before, simply pushes the constant `5` on the stack:

```
stack:
+---------+
| ({}, 5) |
+---------+
|    {}   |
+---------+
|     5   |
+---------+

bindings:
a <- {}
b <- 5
```

Finally:

```
25 STORE_SUBSCR
```

This is where the magic happens. `STORE_SUBSCR` is an instruction to set element on the dictionary given the index. Here's the code that handles this opcode in the eval loop:

```
TARGET_NOARG(STORE_SUBSCR)
{
    w = TOP();
    v = SECOND();
    u = THIRD();
    STACKADJ(-3);
    /* v[w] = u */
    err = PyObject_SetItem(v, w, u);
    Py_DECREF(u);
    Py_DECREF(v);
    Py_DECREF(w);
    if (err == 0) DISPATCH();
    break;
}
```

Here, `TOP`, `SECOND`, `THIRD` are macros that take values off of the value stack. Given our state of the virtual machine:
* `w = TOP()` => `w = 5`
* `v = SECOND()` => `v = {}`
* `w = THIRD()` => `w = ({}, 5)`, but keep in mind, the first element in `w` (the tuple) is actually the same object `v` is pointing to.

Thus, calling `PyObject_SetItem(v, w, u)` sets `v[w] = u` => `v[5] = (v, 5)`, and there a circular reference is born!

From the sequence of operation, we can tell the order by which the assignments were executed:
1. `a, b = {}, 5`
2. `a[5] = ({}, 5)`, with `a` refering to the dictionary

## Conclusion

Diving into the Python implementation is the next level ninjary that may come in handy in some cases. Granted, no one is going to write production code like the one in the puzzler, but stepping through and visualizing the virtual machine is a pretty useful and fun experience that makes me appreciate more the language I use everyday.

Again, thanks to Philip Guo for the videos and Michael Kennedy for the podcast. Also, checkout Professor Guo's [python tutor](http://www.pythontutor.com/) for visualizing how code is run.
