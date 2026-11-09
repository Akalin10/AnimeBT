"""User-scoped Windows DPAPI for GUI credentials."""

import ctypes
from ctypes import wintypes
import sys


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _transform(data, protect):
    if sys.platform != "win32":
        raise OSError("安全保存 API Key 需要 Windows")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    function.argtypes = (ctypes.POINTER(Blob), wintypes.LPCWSTR if protect else ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob))
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buffer), Blob()
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def protect(data):
    return _transform(data, True)


def unprotect(data):
    return _transform(data, False)
