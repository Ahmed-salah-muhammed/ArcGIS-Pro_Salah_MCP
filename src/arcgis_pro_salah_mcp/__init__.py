"""ArcGIS Pro Salah MCP.

A three-layer Model Context Protocol server that lets Claude drive the whole
ArcGIS stack end to end:

    Layer 1 — Pro     : ArcPy geoprocessing on .aprx projects & geodatabases.
    Layer 2 — Portal  : ArcGIS API for Python -> ArcGIS Online / Enterprise
                        (publish layers, manage items, build web maps).
    Layer 3 — WebApp  : generate a static ArcGIS Maps SDK for JavaScript app
                        that renders the published layers as widgets/components.

The typical agent workflow is:  Pro (ArcPy)  ->  Portal (publish)  ->  WebApp.
"""

__version__ = "0.1.0"
