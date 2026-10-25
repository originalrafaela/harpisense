"""Windows physical/commit pressure and counters for the owned native process."""
import ctypes
import os

MIB = 1024**2


def available_memory():
    if os.name != "nt":
        return None

    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]

    class Performance(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in
            ("commit_total", "commit_limit", "commit_peak", "physical_total", "physical_available",
             "system_cache", "kernel_total", "kernel_paged", "kernel_nonpaged", "page_size")
        ] + [(name, ctypes.c_ulong) for name in ("handles", "processes", "threads")]

    value, perf = Memory(), Performance()
    value.length = ctypes.sizeof(value)
    perf.cb = ctypes.sizeof(perf)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError("memory inspection failed")
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(perf), perf.cb):
        raise OSError("commit inspection failed")
    return {"total_bytes": value.total, "available_bytes": value.available,
            "commit_total_bytes": perf.commit_total * perf.page_size,
            "commit_limit_bytes": perf.commit_limit * perf.page_size,
            "commit_headroom_bytes": (perf.commit_limit - perf.commit_total) * perf.page_size}


def process_memory(process):
    if os.name != "nt" or process is None:
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in
            ("peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
             "pagefile", "peak_pagefile", "private")]

    value = Counters()
    value.cb = ctypes.sizeof(value)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.c_void_p(int(process._handle)), ctypes.byref(value), value.cb):
        raise OSError("process memory inspection failed")
    return {"working_set_bytes": value.ws, "peak_working_set_bytes": value.peak_ws,
            "private_bytes": value.private, "peak_commit_bytes": value.peak_pagefile}


class MemoryPolicy:
    def __init__(self, start_mb=3584, commit_start_mb=3072, stop_mb=768,
                 sustained_mb=1024, commit_stop_mb=1024, process_mb=2304):
        if any(type(n) is not int for n in
               (start_mb, commit_start_mb, stop_mb, sustained_mb, commit_stop_mb, process_mb)):
            raise ValueError("memory limits must be integer MiB")
        if (start_mb < 3072 or commit_start_mb < 2560 or stop_mb < 512
                or sustained_mb < stop_mb or start_mb < sustained_mb + 2048
                or commit_stop_mb < 768 or process_mb < 1536):
            raise ValueError("invalid experimental memory profile")
        self.start_mb, self.commit_start_mb = start_mb, commit_start_mb
        self.stop_mb, self.sustained_mb = stop_mb, sustained_mb
        self.commit_stop_mb, self.process_mb = commit_stop_mb, process_mb

    def entry_reason(self, sample):
        if not sample:
            return "memory_inspection_unavailable"
        if sample["available_bytes"] < self.start_mb * MIB:
            return "insufficient_available_memory"
        if sample.get("commit_headroom_bytes", 0) < self.commit_start_mb * MIB:
            return "insufficient_commit_headroom"
        return None

    def pressure_reason(self, system, process, low_count):
        if not system or not process:
            return "memory_inspection_unavailable", 0
        low_count = low_count + 1 if system["available_bytes"] < self.sustained_mb * MIB else 0
        if system["available_bytes"] < self.stop_mb * MIB or low_count >= 3:
            return "physical_memory_pressure", low_count
        if system["commit_headroom_bytes"] < self.commit_stop_mb * MIB:
            return "commit_memory_pressure", low_count
        if max(process["working_set_bytes"], process["private_bytes"]) > self.process_mb * MIB:
            return "owned_process_memory_limit", low_count
        return None, low_count
