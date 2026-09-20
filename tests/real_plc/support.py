"""S7CommPlus helpers for safe real-PLC acceptance scenarios."""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from s7commplus import Client

DB_SIZE = 37
OFFSET_INT1 = 0
OFFSET_INT2 = 2
OFFSET_FLOAT1 = 4
OFFSET_FLOAT2 = 8
OFFSET_BYTE1 = 12
OFFSET_BYTE2 = 13
OFFSET_WORD1 = 14
OFFSET_WORD2 = 16
OFFSET_DWORD1 = 18
OFFSET_DWORD2 = 22
OFFSET_DINT1 = 26
OFFSET_DINT2 = 30
OFFSET_CHAR1 = 34
OFFSET_CHAR2 = 35
OFFSET_BOOLS = 36

EXPECTED_INT1 = 10
EXPECTED_INT2 = 255
EXPECTED_FLOAT1 = 123.45
EXPECTED_FLOAT2 = 543.21
EXPECTED_BYTE1 = 0x0F
EXPECTED_BYTE2 = 0xF0
EXPECTED_WORD1 = 0xABCD
EXPECTED_WORD2 = 0x1234
EXPECTED_DWORD1 = 0x12345678
EXPECTED_DWORD2 = 0x89ABCDEF
EXPECTED_DINT1 = 2147483647
EXPECTED_DINT2 = 42
EXPECTED_CHAR1 = "F"
EXPECTED_CHAR2 = "-"
EXPECTED_BOOLS = (True, False, False, False, False, False, False, False)

MetadataValue = str | int | bool


@dataclass(frozen=True)
class PLCConfig:
    """Connection settings; sensitive values are deliberately not reportable."""

    host: str
    port: int
    rack: int
    slot: int
    read_db: int
    write_db: int
    use_tls: bool
    tls_cert: str | None
    tls_key: str | None
    tls_ca: str | None


class PLCAdapter(Protocol):
    """Small surface used by the Gherkin acceptance scenarios."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    def read(self, db_number: int, offset: int, size: int) -> bytes: ...

    def write(self, db_number: int, offset: int, data: bytes) -> None: ...

    def read_multi(self, db_number: int, regions: Sequence[tuple[int, int]]) -> list[bytes]: ...

    def runtime_metadata(self) -> dict[str, MetadataValue]: ...


class S7CommPlusAdapter:
    def __init__(self, config: PLCConfig) -> None:
        self.config = config
        self.client = Client()

    def connect(self) -> None:
        self.client.connect(
            self.config.host,
            port=self.config.port,
            rack=self.config.rack,
            slot=self.config.slot,
            use_tls=self.config.use_tls,
            tls_cert=self.config.tls_cert,
            tls_key=self.config.tls_key,
            tls_ca=self.config.tls_ca,
        )

    def disconnect(self) -> None:
        self.client.disconnect()

    def is_connected(self) -> bool:
        return self.client.connected

    def read(self, db_number: int, offset: int, size: int) -> bytes:
        return self.client.db_read(db_number, offset, size)

    def write(self, db_number: int, offset: int, data: bytes) -> None:
        self.client.db_write(db_number, offset, data)

    def read_multi(self, db_number: int, regions: Sequence[tuple[int, int]]) -> list[bytes]:
        return self.client.db_read_multi([(db_number, offset, size) for offset, size in regions])

    def runtime_metadata(self) -> dict[str, MetadataValue]:
        return {
            "protocol_path": "s7commplus",
            "protocol_version": f"V{self.client.protocol_version}",
            "tls_enabled": self.client.tls_active,
            "tls_client_certificate": self.config.tls_cert is not None,
            "tls_ca_verification": self.config.tls_ca is not None,
        }


def make_adapter(config: PLCConfig) -> PLCAdapter:
    return S7CommPlusAdapter(config)


def canonical_fixture_bytes() -> bytes:
    """Return the canonical 37-byte non-optimized DB image."""
    return b"".join(
        (
            struct.pack(
                ">hhffBBHHIIii",
                EXPECTED_INT1,
                EXPECTED_INT2,
                EXPECTED_FLOAT1,
                EXPECTED_FLOAT2,
                EXPECTED_BYTE1,
                EXPECTED_BYTE2,
                EXPECTED_WORD1,
                EXPECTED_WORD2,
                EXPECTED_DWORD1,
                EXPECTED_DWORD2,
                EXPECTED_DINT1,
                EXPECTED_DINT2,
            ),
            EXPECTED_CHAR1.encode() + EXPECTED_CHAR2.encode() + bytes([1]),
        )
    )


def assert_canonical_fixture(data: bytes) -> None:
    """Validate every documented scalar in the canonical fixture."""
    assert len(data) == DB_SIZE
    assert struct.unpack_from(">h", data, OFFSET_INT1)[0] == EXPECTED_INT1
    assert struct.unpack_from(">h", data, OFFSET_INT2)[0] == EXPECTED_INT2
    assert math.isclose(struct.unpack_from(">f", data, OFFSET_FLOAT1)[0], EXPECTED_FLOAT1, abs_tol=0.001)
    assert math.isclose(struct.unpack_from(">f", data, OFFSET_FLOAT2)[0], EXPECTED_FLOAT2, abs_tol=0.001)
    assert data[OFFSET_BYTE1] == EXPECTED_BYTE1
    assert data[OFFSET_BYTE2] == EXPECTED_BYTE2
    assert struct.unpack_from(">H", data, OFFSET_WORD1)[0] == EXPECTED_WORD1
    assert struct.unpack_from(">H", data, OFFSET_WORD2)[0] == EXPECTED_WORD2
    assert struct.unpack_from(">I", data, OFFSET_DWORD1)[0] == EXPECTED_DWORD1
    assert struct.unpack_from(">I", data, OFFSET_DWORD2)[0] == EXPECTED_DWORD2
    assert struct.unpack_from(">i", data, OFFSET_DINT1)[0] == EXPECTED_DINT1
    assert struct.unpack_from(">i", data, OFFSET_DINT2)[0] == EXPECTED_DINT2
    assert chr(data[OFFSET_CHAR1]) == EXPECTED_CHAR1
    assert chr(data[OFFSET_CHAR2]) == EXPECTED_CHAR2
    assert tuple(bool(data[OFFSET_BOOLS] & (1 << bit)) for bit in range(8)) == EXPECTED_BOOLS


WRITE_VALUES: dict[str, tuple[int, bytes, Callable[[bytes], object], object]] = {
    "INT": (0, struct.pack(">h", -1234), lambda data: struct.unpack(">h", data)[0], -1234),
    "REAL": (4, struct.pack(">f", 456.75), lambda data: struct.unpack(">f", data)[0], 456.75),
    "BYTE": (12, b"\xa5", lambda data: data[0], 0xA5),
    "WORD": (14, struct.pack(">H", 0x5AA5), lambda data: struct.unpack(">H", data)[0], 0x5AA5),
    "DWORD": (18, struct.pack(">I", 0xDEADBEEF), lambda data: struct.unpack(">I", data)[0], 0xDEADBEEF),
    "DINT": (26, struct.pack(">i", -123456789), lambda data: struct.unpack(">i", data)[0], -123456789),
    "CHAR": (34, b"X", lambda data: chr(data[0]), "X"),
    "BOOL": (36, b"\x81", lambda data: bool(data[0] & 0x80), True),
}


class ScratchRestoreGuard:
    """Save, restore, and verify one scratch region; restoration is idempotent."""

    def __init__(self, adapter: PLCAdapter, db_number: int, offset: int, size: int) -> None:
        self.adapter = adapter
        self.db_number = db_number
        self.offset = offset
        self.original = adapter.read(db_number, offset, size)
        self.restored = False

    def restore(self) -> None:
        if self.restored:
            return
        self.adapter.write(self.db_number, self.offset, self.original)
        restored = self.adapter.read(self.db_number, self.offset, len(self.original))
        if restored != self.original:
            raise AssertionError("scratch DB restoration verification failed")
        self.restored = True
