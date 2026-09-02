"""
Shared service-layer errors.

The project's governing constraint is that a number leaving this API is either
a real model output or is absent - never a plausible-looking stand-in. So when
the trained checkpoint or the ingested data a service needs is missing, it
raises RealDataUnavailable and the route turns that into a 503 with the reason
attached, instead of falling back to a simulated curve the dashboard would
render identically to a real one.
"""


class RealDataUnavailable(RuntimeError):
    """Raised when a service cannot produce a genuine model-derived answer."""
