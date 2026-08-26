FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y tor && \
    rm -rf /var/lib/apt/lists/*

COPY torrc /etc/tor/torrc

# Onion service directories need strict permissions
RUN mkdir -p /var/lib/tor/hidden_service_marketplace /var/lib/tor/hidden_service_vulnerable && \
    chown -R debian-tor:debian-tor /var/lib/tor && \
    chmod -R 700 /var/lib/tor

USER debian-tor

CMD ["tor", "-f", "/etc/tor/torrc"]
