import ctypes
l = ctypes.CDLL("/opt/hostnvidia/libcuda.so.1")
print("dlopen host libcuda OK")
r = l.cuInit(0)
print("cuInit ret =", r)
if r == 0:
    n = ctypes.c_int()
    l.cuDeviceGetCount(ctypes.byref(n))
    print("devices =", n.value)
