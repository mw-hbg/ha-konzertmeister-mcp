"""Restrict the MCP server to the few folders it needs (Linux Landlock).

The server runs as an unprivileged user already. Landlock additionally lets it
give up access to every file and folder that is not listed below – even
folders that are readable for everyone, such as the Home Assistant
configuration folder mapped into the container. The restriction is applied
by the server process to itself, cannot be lifted afterwards and is inherited
by every child process.

If the kernel or the container runtime does not offer Landlock, nothing is
restricted beyond the unprivileged user (logged once).
"""

from __future__ import annotations

import ctypes
import logging
import os

log = logging.getLogger("konzertmeister_mcp_app.sandbox")

# Syscall numbers are the same on x86_64 and aarch64 (generic table).
_SYS_CREATE_RULESET = 444
_SYS_ADD_RULE = 445
_SYS_RESTRICT_SELF = 446
_PR_SET_NO_NEW_PRIVS = 38
_RULE_PATH_BENEATH = 1
_CREATE_RULESET_VERSION = 1

# Access rights (ABI 1–3)
EXECUTE = 1 << 0
WRITE_FILE = 1 << 1
READ_FILE = 1 << 2
READ_DIR = 1 << 3
REMOVE_DIR = 1 << 4
REMOVE_FILE = 1 << 5
MAKE_CHAR = 1 << 6
MAKE_DIR = 1 << 7
MAKE_REG = 1 << 8
MAKE_SOCK = 1 << 9
MAKE_FIFO = 1 << 10
MAKE_BLOCK = 1 << 11
MAKE_SYM = 1 << 12
REFER = 1 << 13  # ABI 2
TRUNCATE = 1 << 14  # ABI 3

_FILE_RIGHTS = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE
READ_ONLY = EXECUTE | READ_FILE | READ_DIR

# Read-only: the system and Python itself, the app's code, process info.
READ_PATHS = ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/app", "/proc", "/sys", "/dev")
# Writable files outside the folders below.
WRITE_FILES = ("/dev/null", "/dev/urandom", "/dev/random", "/dev/tty")


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _handled(abi: int) -> int:
    rights = (MAKE_SYM << 1) - 1  # ABI 1: bits 0–12
    if abi >= 2:
        rights |= REFER
    if abi >= 3:
        rights |= TRUNCATE
    return rights


def restrict(write_dirs: list[str], read_dirs: tuple[str, ...] = READ_PATHS) -> bool:
    """Allow reading read_dirs and full access to write_dirs, deny the rest.

    Returns True if the restriction is active."""
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(_SYS_CREATE_RULESET, None, ctypes.c_size_t(0), ctypes.c_uint32(_CREATE_RULESET_VERSION))
    if abi < 1:
        # Expected on Home Assistant OS (its kernel has no Landlock) – not an error.
        log.info(
            "Landlock is not available here (errno %d) – the MCP server stays limited by its"
            " unprivileged user and the AppArmor profile",
            ctypes.get_errno(),
        )
        return False
    handled = _handled(abi)
    attr = _RulesetAttr(handled)
    ruleset = libc.syscall(_SYS_CREATE_RULESET, ctypes.byref(attr), ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint32(0))
    if ruleset < 0:
        log.warning("Landlock ruleset could not be created (errno %d)", ctypes.get_errno())
        return False
    try:
        def allow(path: str, rights: int) -> None:
            try:
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except OSError:
                return  # path does not exist in this image – nothing to allow
            try:
                if not os.path.isdir(path):
                    rights &= _FILE_RIGHTS
                rule = _PathBeneathAttr(rights & handled, fd)
                if libc.syscall(_SYS_ADD_RULE, ruleset, ctypes.c_int(_RULE_PATH_BENEATH), ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
                    raise OSError(ctypes.get_errno(), f"Landlock rule for {path} failed")
            finally:
                os.close(fd)

        for path in read_dirs:
            allow(path, READ_ONLY)
        for path in WRITE_FILES:
            allow(path, READ_FILE | WRITE_FILE)
        for path in write_dirs:
            allow(path, handled)
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "no_new_privs failed")
        if libc.syscall(_SYS_RESTRICT_SELF, ruleset, ctypes.c_uint32(0)) != 0:
            raise OSError(ctypes.get_errno(), "Landlock restrict_self failed")
    finally:
        os.close(ruleset)
    log.info("Landlock active (ABI %d): the MCP server can only reach its own folders", abi)
    return True
