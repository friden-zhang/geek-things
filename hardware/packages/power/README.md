# Power Packages

Put reusable power trees, input protection, regulators, supervisors, and rail monitoring blocks here.

Any block that may be shared between two boards because it solves the same power problem belongs here instead of inside a single board directory.

Current package:

- `usb_c_5v_input.ato`: horizontal USB-C sink entry that exposes both `USB2_0` data and a named `vbus_5v` rail.
- `ap2112k_3v3_ldo.ato`: concrete AP2112K-3.3 fixed LDO stage with local input/output stability capacitors.
