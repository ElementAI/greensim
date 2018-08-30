Any time a variable is accessed as an attribute, the underlying method `__get__` is called on the variable

```
>>> class A:
...     def __get__(*args):
...         print("Getting an A")
... 
>>> class B:
...     a = A()
... 
>>> B.a
Getting an A
```

See: https://docs.python.org/3.7/howto/descriptor.html#id5

This method can also take arguments, which affect the scope into which the requested variable is bound. If an object instance is provided as the first argument, the variable on which `__get__` was called will be bound to the scope of that instance

```
>>> class A:
...     def __init__(self):
...         self.message = "I'm from A"
... 
>>> class B:
...     def print_message(self):
...         print(self.message)
...         print(self.__class__)
...

>>> B().print_message()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<stdin>", line 3, in print_message
AttributeError: 'B' object has no attribute 'message'


>>> B.print_message.__get__(A())
<bound method B.print_message of <__main__.A object at 0x7fa4f1e8f860>>


>>> B.print_message.__get__(A())()
I'm from A
<class '__main__.A'>
```

See: https://docs.python.org/3.7/reference/datamodel.html?highlight=metaclass#implementing-descriptors

Notice how above, the instance `B()` does not normally have access to `message`, but by giving the `__get__` method an instance `A()`, which does have `message`, the method `print_message` from `B` was returned, bound to the scope of the `A()` instance. Thus, when it was called, the instance `A()` was used as the scope and the `message` variable was readily accessed. The `print(self.__class__)` call is used to prove that the method is running on the `A()` instance (since the result is `<class '__main__.A'>`), as opposed to giving the `B` object access to the `message` variable

This pattern is used by the `super()` method to bind the `__init__` of the parent class to the context of the child, and can be used directly by the programmer if desired:

```
>>> class A(object):
...     def __init__(self):
...         self.a = "Living in an A"
... 
>>> class B(A):
...     def __init__(self):
...         super().__init__()
...         print(self.a)
... 
>>> class C(A):
...     def __init__(self):
...         A.__init__.__get__(self)()
...         print(self.a)
... 
>>> isinstance(B(), A)
Living in an A
True
>>> isinstance(C(), A)
Living in an A
True
```

See: https://docs.python.org/3.7/reference/datamodel.html?highlight=metaclass#invoking-descriptors

This is typically not necessary, but in the case of multiple inheritance it has the benefit of directly specifying the `__init__` method that should be called, rather than letting Python search `__mro__` with its own pattern. This is used in the `Process` constructor in order to make sure that both the constructors for `greenlet.greenlet` and `TaggedObject` are called, since without both calls the `Process` object would be improperly initialized and unusual behavior would result.

The reason this was required was that a bug emerged where Tags would persist across `Process` objects in unexpected ways. This was patched incorrectly in https://github.com/ElementAI/greensim/commit/3dd1a50c00002703de825577c49cae256bd91644

As it turns out, if the super class is not properly initialized, it can persist values across multiple instantiations of its subclasses. An example is provided below.

```
>>> class A(object):
...     def update(self):
...         self.a = 1
... 
>>> class B(A):
...     def call_update(self):
...         self.update()
...     def print_a(self):
...         print(self.a)
... 
>>> b = B()
>>> b.print_a()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<stdin>", line 5, in print_a
AttributeError: 'B' object has no attribute 'a'
>>> b.call_update()
>>> b.print_a()
1
>>> bb = B()
>>> b.print_a()
1
```


Other reading:

https://docs.python.org/3.7/reference/executionmodel.html?highlight=binding#resolution-of-names
