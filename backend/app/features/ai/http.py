"""
Shared HTTP Client Setup For Direct Provider Integrations

The providers litellm doesn't support (Arcana, Cartesia, Google Cloud TTS, GWDG SAIA) are called
directly over httpx. Each integration module creates its own client once via make_ipv4_client().
"""

import httpx


def make_ipv4_client() -> httpx.Client:
    """A long-lived httpx client that only connects over IPv4.

    Forces IPv4: some networks advertise IPv6 addresses for a host that are actually unreachable
    (routed nowhere, not even rejected) — httpx tries every resolved address in order and eats
    the full per-address timeout on each dead one before falling back to IPv4, which can turn a
    healthy timeout into several minutes. Binding the local address to the IPv4 wildcard makes
    httpx skip IPv6 candidates entirely instead of hanging on them one by one.

    Create it once and never close it, instead of a fresh "with httpx.Client(...)" per call: a
    Client passed an explicit transport= doesn't own a private copy of it, so closing the Client
    on a `with`-exit closes the connection pool for every concurrent caller sharing the same
    transport too (confirmed against the installed httpx/httpcore source — .close() force-closes
    every connection currently on the pool, active or idle, not just this call's own). A single
    long-lived Client both avoids that and gives every call real keep-alive.
    """
    return httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"))
