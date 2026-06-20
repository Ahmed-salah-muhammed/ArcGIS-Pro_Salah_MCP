"""Layer 1b — Live ArcGIS Pro session tools (the open desktop session).

ArcPy cannot attach to a *running* ArcGIS Pro session, so the live_* tools talk
over loopback HTTP to a .NET add-in (``ProSalahBridge/``) running inside Pro. This
package is the Python client side of that bridge; the C# side and the wire
contract live in ``ProSalahBridge/`` and ``docs/PROTOCOL.md``.
"""
