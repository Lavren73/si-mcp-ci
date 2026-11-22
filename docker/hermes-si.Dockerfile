# Hermes + SI-MCP test toolchain (Lavren73, 2026-11-22)
# Temurin JDK17 (as CI) + Maven + gh + pnpm baked in; survives container recreation.
FROM nousresearch/hermes-agent:latest
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      maven ca-certificates curl gnupg && \
    install -dm 0755 /etc/apt/keyrings && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    chmod 0644 /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse" -o /tmp/jdk17.tar.gz && \
    mkdir -p /opt/jdk-17 && tar -xzf /tmp/jdk17.tar.gz -C /opt/jdk-17 --strip-components=1 && rm /tmp/jdk17.tar.gz && \
    npm install -g pnpm
ENV JAVA_HOME=/opt/jdk-17
ENV PATH=/opt/jdk-17/bin:${PATH}
# pnpm lands in the pinned node tool dir, which is not on the service PATH;
# symlink into /usr/local/bin so `pnpm` resolves for the hermes user.
RUN ln -sf /opt/hermes/tools/node-*/bin/pnpm /usr/local/bin/pnpm && \
    ln -sf /opt/hermes/tools/node-*/bin/pnpx /usr/local/bin/pnpx
