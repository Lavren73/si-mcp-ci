# Hermes + SI-MCP full test toolchain (Lavren73, 2026-11-22)
# Temurin JDK17 (as CI) + Maven + gh + pnpm + xvfb/GTK for 1C:EDT and headless OSGi tests.
#
# NOT baked into this image (private, host-side bind mounts at `docker run`):
#   ~/hermes-tools  -> /opt/tools   1C platform, EDT, YAxUnit, Vanessa, bin/ launchers
#   ~/hermes-data   -> /opt/data    Hermes profile incl. .1cv8/1C/1cv8/conf/*.lic (1C software license)
# The 1C license is hardware-bound; copying the .lic between containers on the SAME host
# may work, otherwise re-activate with the pin code (see docker/README.md). No secrets here.
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
# --- 1C:EDT / SWT / headless OSGi test runtime (Debian 13 trixie, t64 libs) ---
# xvfb-run wraps `mvn verify` (Tycho surefire needs a display); GTK3+WebKit run the EDT IDE.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      xvfb xauth libgtk-3-0t64 libxtst6 libxi6 libxrender1 libxext6 libx11-6 libxcb1 \
      libwebkit2gtk-4.1-0 libgl1 libegl1 libgbm1 libsecret-1-0 libasound2t64 libnss3 \
      fontconfig fonts-dejavu-core libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libpango-1.0-0 libcairo2 libdrm2 libatk1.0-0t64 libatk-bridge2.0-0t64 \
      libcups2t64 libxss1 libglib2.0-0t64 libgdk-pixbuf-2.0-0 && \
    rm -rf /var/lib/apt/lists/*
# Launchers for the mounted test stack live in /opt/tools/bin (private bind, editable
# without rebuilding): 1cv8/1cv8c/1cv8s -> 1C platform; 1cedt/1cedtcli -> EDT (bundled Java 25).
ENV PATH=/opt/tools/bin:${PATH}
RUN printf '%s\n' 'export PATH=/opt/tools/bin:$PATH' '# 1C license: /opt/data/.1cv8 ; test stack: /opt/tools' > /etc/profile.d/si-tools.sh