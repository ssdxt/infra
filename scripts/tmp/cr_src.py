import inspect, mineru.utils.config_reader as cr
src = inspect.getsource(cr)
print(src[:2600])
