# Answers to the open questions in the code

Hi. This is a reply from an independent reverse engineering effort on the same
protocol. We run our own branch (`s7complus_re`) against a PLCSIM S7-1500
(FW 2.9, S2.9 firmware string) with MITM captures of real TIA Portal traffic.
Everything below comes from byte level golden captures taken in September 2026,
plus some TIA decompile reads. Where we have no data, we say so.

Golden frames that back these answers are in
`tests/fixtures/golden_tia_online_session_20260915.py`. Each frame is verbatim
TIA Portal to PLC traffic. Feel free to diff your own captures against them.

## 1. The unknown flag in the EXPLORE request

`client.py`, `_build_explore_request`, the byte after ExploreChildsRecursive:

```python
payload += bytes([1])  # unknown flag - the protocol always carries 1 here
```

Answer: your byte order is right and your value works, but the flag is not
always 1. We captured three different TIA EXPLORE requests:

```
device tree explore   childs=1, flag=1, parents=0
event tree explore    childs=1, flag=0, parents=1   (58 attributes)
pair explore          childs=1, flag=0, parents=1   (zero attributes)
```

The event tree response contains both the children of rid 3 and the parent
ASRoot, which pins the order as childs, flag, parents. So the byte sits
between ExploreChildsRecursive and ExploreParents. TIA sends 1 on the device
tree explore and 0 on the event tree and pair explores. We cannot name the
semantic yet. Hard coding 1 is fine for plain attribute explores, your field
use proves that. A TIA faithful client would pick 0 for explore shapes like
the event tree one.

The full body layout we see on the wire:

```
ExploreId            u32 fixed
ExploreRequestId     VLQ
ExploreChildsRecursive  1 byte
<flag>               1 byte, see values above
ExploreParents       1 byte
NumberOfFollowingFilterObjects  VLQ
AddressListCount     VLQ
AddressIds           VLQ each
KeyQualifier         VLQ (optional, see below)
fill                 u32 zero + 1 zero byte
```

Two extra observations:

- The attribute ids are plain VLQ values. An early read of TIA traffic made us
  label them u16, which was wrong. VLQ decoding is confirmed by the response
  side: `a3 81 69` is attribute 233 (ObjectVariableTypeName), and 233 as VLQ is
  exactly `81 69`.
- TIA also carries a trailing KeyQualifier VLQ between the address list and
  the fill. In our captures it holds the running read counter of the session
  (33 for the ASRoot explore, 34 for the pair explore, 4 for the upload
  explore). You already track this as the IntegrityId and splice it in with
  `integrity_tail=5`, which lands in the same place. Good.

## 2. The trailing bytes of the ObjectQualifier and the SetVariable payload

`codec.py`, `encode_object_qualifier`, and `connection.py`,
`_build_set_variable_payload`:

```python
result += encode_uint32_vlq(key_qualifier)
result += bytes([0x00])          # in encode_object_qualifier, V2 path
...
payload += encode_object_qualifier()
payload += bytes([0x00])         # protocol-defined unknown byte
```

Answer: TIA is more terse than the reference C# driver here. Decoding a golden
TIA SetMultiVariables (subscription registration, sequence 0x98):

```
... items ...
00 00 04 e8      ObjectQualifier id 1256, fixed u32
89 69            ParentRID id 1257
00 12 00 00 00 00   flags 00, datatype RID(0x12), value 0
89 6a            CompositionAID id 1258
00 13 00         flags 00, datatype AID(0x13), value 0
89 6b            KeyQualifier id 1259
00 04 13         flags 00, datatype UDInt(0x04), value 19 (the running write counter)
00 00 00 00      4 byte fill, IntegrityId spliced in front of it
```

So TIA puts nothing between the KeyQualifier value and the 4 byte fill. The
0x00 terminators in your encoder (and the extra one in
`_build_set_variable_payload`) are reference driver behavior. Real PLCs accept
both shapes, your legitimation and data access work in the field, and our
client sends the terse TIA shape and works too. The parser on the PLC side is
lenient about trailing terminators. If you ever chase byte exact TIA parity,
that is the delta. Otherwise leave it.

One refinement that matters more: your docstring says TIA sets the
KeyQualifier to the current sequence number. From our field runs the real rule
is: it is the per direction request counter. Reads carry the read counter,
writes carry the write counter, and they advance independently. Replaying a
captured counter that is ahead of the session (a jump) makes the PLC reset the
TCP connection on the spot. We lost weeks to that. Details in section 8.

## 3. The unknown padding in the NullServerSession CreateObject

`connection.py`, `_build_create_object_null_server_session`:

```python
# Unknown padding (always 0)
request += struct.pack(">I", 0)
```

Answer: TIA confirmed. The golden TIA session CreateObject (sequence 2, the
ServerSession_2DC6C1 create) decodes as:

```
00 00 01 1d      RequestId 285 (ObjectServerSessionContainer)
00 04 00         RequestValue, flags 00, UDInt, VLQ 0
00 00 00 00      the same u32 padding you send
a1 ...           StartOfObject
```

So the u32 zero between RequestValue and the request object is real TIA
traffic. Constant 0 in every create we captured. Keep it.

## 4. The unknown byte after ReturnValue in GVS responses

`server.py`, `_handle_get_var_substreamed`:

```python
response += encode_uint64_vlq(0)  # ReturnValue: success
response += bytes([0x00])         # protocol-defined unknown byte
```

Answer: this matches what real PLCs send us, at least for the requests we
captured. Our golden GVS response (the firmware component table poll) decodes
as flags 0x34, retval VLQ 00, then a 00 byte, then the body markers. A golden
SetMultiVariables response does the same: retval VLQ 00, then 00, then the
per item ReturnValue elements. One caveat from a golden SetVarSubStreamed
response: there the byte after the retval is 0x0d, not 0x00. So the byte is
real and sits right after the ReturnValue, but it is not a constant across
function codes. Treat it as a per response field you should capture and echo,
not as a fixed zero.

## 5. The three UInt16 fields in notification frames

`alarm.py`, `parse_alarm_notification`:

```python
offset += 10  # subscription id plus three unknown UInt16 fields
```

Answer: we have two content bearing TIA notification frames captured on the
wire (one CPU state notification on subscription rid 0x7000103f, one diagnostic
event notification on rid 0x70001040). Both carry the same 6 bytes:

```
04 00 00 00 00 00
```

That is u16 0x0004 followed by two zero u16s. The 0x0004 is stable across two
different subscription objects and two different notification payloads, so it
is not a counter and not a length. Our guess is a notification format version
marker. Your skip of 6 bytes is correct and safe.

What comes after those 6 bytes differs per notification family, and this is
where we can save you some pain:

Event / data notifications (what TIA gets from its online status and
diagnostic event subscriptions, function class 1):

```
subscription id   u32
04 00 00 00 00 00
00                1 byte
seq               VLQ (2 on a fresh sub, 531 = 84 13 on a busy one)
00                1 byte
timestamp block   8 bytes (epoch unknown, see below)
records           0x92 element + id u32 + PValue, repeated
```

Alarm notifications (your family, offsets ported from upstream and proven on
real PLCs): credit tick, seq VLQ, change counter, timestamp plus one extra
byte when the change counter is zero.

These two grammars are not interchangeable. If we feed our CPU state event
notification into the alarm parser it reads credit tick 0x00, seq 2, change
counter 0, then a u64 timestamp, then expects one more byte and lands one byte
into the record list. Your parser would raise on it, which is fine, it is not
an alarm frame. Just keep the families separate and do not "fix" the alarm
offsets based on event frames.

About the 8 byte timestamp block: the high bytes are shared between two frames
captured minutes apart, so it is a counter or timestamp with a coarse unit. We
could not map it to unix time, filetime, or NTP with the data we have. Still
open on our side too.

## 6. The 0x81 check in the alarm notification

`alarm.py`, the `data[offset] != 0x81` raise.

No new data from us. We ported the alarm grammar from the same upstream sources
you did and our field PLC never pushed a real alarm notification during our
capture window (our alarm subscription work ran against a dummy PLC with canned
frames). 0x81 is the ReturnValue element id, so your check is element id plus
implicit value. Nothing to add, sorry.

## 7. The session auth blob metadata unknown1 and unknown2

`session_auth/blob_metadata.py`, `unknown1` and `unknown2`, always 1.

Out of our observation set. Our session path goes through TLS 1.3 with the OMS
exporter key derivation (`EXPERIMENTAL_OMS` label, 32 bytes) and password
legitimation. We never decoded the session key blob format, we reuse your
HarpoS7 derived work for nothing and our PLC accepts the TLS exporter path
directly. So we cannot answer this one. Someone with S7-1200 session key
captures needs to fill it in.

## 8. Things we learned the hard way that are not in your docs yet

This is the part that might save you the most time. All of it is field proven
against PLCSIM S7-1500 FW 2.9 with TIA as the golden client.

### The disconnect after symbolic access has a root cause

Your troubleshooting doc says "Some firmware resets a session after particular
symbolic reads". We root caused this one. It is not the symbolic read itself.
Two separate things:

- The KeyQualifier / IntegrityId counters. If a request carries a counter
  value that is ahead of the session's real counter (for example when you
  replay a captured TIA request verbatim), the PLC kills the TCP connection
  with a RST immediately. Reads and writes have separate counters.
- SetVarSubStreamed on the monitoring session. TIA never writes symbols over
  the connection that carries the cyclic subscription. It opens a third short
  lived connection (the watch table session), does the write there, and tears
  it down. If you write on the subscription session, the PLC resets you, even
  when every byte of the request is correct.

So if an application sees random RSTs after mixed reads, writes and
subscriptions on one connection, split the write traffic onto its own short
lived session and double check the counters. That fixed it for us completely.

### Small 0xFE frames end a response stream

You already decode SystemEvents with a ReturnValue. One more behavior worth
encoding: a small 0xFE frame (no matching response content) acts as the end of
stream marker for a response, and a 0xFE with content is a real event that
must not truncate response collection. We push diagnostic slot tables as
content bearing SystemEvents (16 records of 202 bytes total) right after a
diagnostic subscription create and after the final teardown. If you collect
response frames, only the small 0xFE terminates the stream.

### The diagnostic event tree is explorable and subscribable

The objects TIA renders in Online and diagnostics are plain OMS objects under
ASRoot (rid 3 is PLCProgram, rid 10 is SWEvents, and the event objects are
rids 101 to 113). You can EXPLORE them like anything else and subscribe to
their attributes. The subscription create carries two qualifier counters (the
write slot before the rid, and the client subscription counter in the
temporary rid 0x7FFFC0xx that also mirrors into the Subscription_21474672xx
name). Registered items ride SetMultiVariables with the address array under
attribute 0x8818. Notifications then arrive on the subscription rid.

From the TIA decompile, the event class ids for those objects, if you want to
type check what you explored:

```
CPUredundancyError 101 -> class 2015
TimeError          102 -> class 2091
DiagnosticError    103 -> class 2027
PullPlugEvent      104 -> class 2062
StartupEvent       107 -> class 2070
ProgrammingError   108 -> class 2107
IOaccessError      109 -> class 2110
MaxCycleTimeError  110 -> class 2111
ProfileEvent       111 -> class 2056
StatusEvent        112 -> class 2075
UpdateEvent        113 -> class 2104
BaseClass          all -> class 3744
```

Also from the decompile: the diagnostic buffer TIA shows under Online and
diagnostics is the ASLog object, class 2448, with LogEntry 2447, LogEntry2
8062, HeadPositionIndicator 3693. Reading aid 8062 on it is on our todo list.

### CPU operating state writes

Your `CPU_EXEC_UNIT_EXECUTING` (8064) and `CPU_EXEC_UNIT_OPERATING_MODE`
(8065) observations match ours, 1/7 in RUN and 0/0 in STOP. One extra from the
decompile: the operating state request enum on the CPU exec unit object is
1 = Stop_REQ, 3 = Run_REQ. A DInt(1) write to that attribute is a stop
request, not a random scalar.

## 9. Small stuff

- `typeinfo.py` unknown tag skip and `codec.py` unknown type skip: fine as is.
  One suggestion, log the byte range at debug level when it happens. New
  datatypes show up first as parse gaps, and a debug log turns a mystery into
  a capture.
- `session_auth/family0/big_int_transforms.py` TODO: that is a HarpoS7
  upstream comment, not ours to answer.

## What we used

- PLCSIM Advanced S7-1500 FW 2.9 on an isolated segment.
- TIA Portal as the golden client, MITM capture between it and the PLC
  (TLS terminated with a pinned proxy, TOFU cert trust).
- TIA Portal decompile for class ids and API shapes, never for wire bytes.
- Our own dummy PLC that replays the golden grammar, so client changes get
  regression tested offline.

The golden frames live in `tests/fixtures/golden_tia_online_session_20260915.py`.
If any answer above does not match a capture of yours, trust your capture and
tell us, that is how everyone learns here. Both projects win when the wire
facts match.
