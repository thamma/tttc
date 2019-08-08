def f():
    print("very secret variable leaked")

def g():
    #h = lambda : (print("hi"), print("hello"))
    yn(f, "leak secret? ")

def yn(task, question):
    x = input(question)
    if x == "y":
        task()

g()
