# Notices and source attribution

The low-level LCD modules in `src/auxdisp_driver/lcd/` are derived from
the device drivers in `mathoudebine/turing-smart-screen-python`, chiefly
copyright (C) 2021 Matthieu Houdebine and additional contributors identified in
the source-file headers. The source was taken from branch `main`, commit
`866e5ba999de0ed9373a46b6f2a714ef8322cfce` (2026-11-09). The source project is
licensed GPL-3.0-or-later; the complete license is included as `LICENSE`.

Changes made in this package include package import paths, a standard library
logger in place of the application's rotating-file logger, fallback to Pillow's
built-in font for the old `res/fonts/...` defaults, and explicit PyUSB resource
disposal for the Turing USB driver. The simulator's HTTP thread and socket have
explicit cleanup. Serial connection exhaustion and USB transfer failures raise
`DisplayError` instead of exiting the application or silently returning. Rev C
discovery supports passive enumeration while preserving the original wake-up
sequence when opening a device or explicitly requesting active discovery.
Device command formats, successful-transfer ordering, and the legacy file-upload
retry are retained. The extraction and these changes are not a certification of
hardware compatibility.

`hchargois/smartscreen-driver` at commit
`918342ecbf33d210d41867f083142e3b5cbffcca` was consulted for packaging and API
organization only. No implementation code from that repository is included.
