# Durable recipe: self-hosted GitHub Actions runner `si1c-docker` (container `si1c-ci`).
#
# Кто/когда/что/почему/основание — агент №1 (Windows), 26.11.2026:
#   задача Lavren73/SI-MCP#640 §5 «закрепить в образе»; правило #40 (кто/когда/что/почему/основание);
#   O-22 — только PR, не мержить.
#   Почему: до этого рецепта образ `si1c-runner:local` существовал только как КОНТЕЙНЕР с ручными
#   правками (docker commit после сборки 2026-11-10). Пересоздание контейнера теряло jdk17, maven,
#   шимы в /usr/local/bin и gh. Теперь всё это воспроизводится из текста.
#
# Состав снят С ЖИВОГО контейнера 26.11.2026 — [ИЗМЕРЕНО] (docker history + инвентарь):
#   Ubuntu 22.04.5 · python 3.10.12 · python3-pytest 6.2.5 · python3-pip 22.0.2 ·
#   build-essential 12.9ubuntu3 · xvfb 2:21.1.4 · libwebkit2gtk-4.0-37 2.50.4
#   Temurin JDK 17.0.21.1 (/home/runner/jdk17, 319M) · Maven 3.9.9 (/home/runner/maven, 11M)
#   /opt/apache-maven-3.9.9 -> /home/runner/maven (жёстко ждёт «сервер-тесты.yml»)
#   gh 2.106.0 (/usr/local/bin/gh — доустановлен в проходе №1, §3)
#   actions-runner 2.338.2 (agentName si1c-docker, agentId 22; _work ~5.6G)
#   /opt/si-edt 7.6G (EDT 2026.2 + Axiom JDK 25) · /opt/1cv8 2.7G (1С 8.3.27.2342)
#   /home/runner/.m2 1.3G — кэш, в образ НЕ входит (регенерируется первым прогоном)
#
# [НЕ ПРОВЕРЕНО]: образ по этому рецепту ещё НЕ собирался. Для сборки в контексте нужны
#   edt.tar.gz (~3.8G) и platform.zip (~1.6G) — они лежат в живом контейнере, но НЕ в git.
#   Забрать их ДО чистки контейнера: см. README.md, раздел «Забрать архивы ПЕРЕД чисткой».
#
# Сборка:
#   cd docker/si1c-runner && docker build -t si1c-runner:local .

FROM ubuntu:22.04

# Версии зафиксированы по замеру; менять осознанно — от них зависят эталоны CI.
ARG RUNNER_VERSION=2.338.2
ARG MAVEN_VERSION=3.9.9
ARG GH_VERSION=2.106.0

ENV DEBIAN_FRONTEND=noninteractive

# ── Слой 1: базовые пакеты ────────────────────────────────────────────────────────────────
# Первая часть списка — ровно тот apt-слой, что виден в `docker history si1c-runner:local`.
# python3-pytest / python3-pip / build-essential доустановлены позже руками (§1 задачи #640),
# поэтому здесь они в том же слое — так дешевле и воспроизводимо.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git tar gzip unzip python3 gosu procps \
      python3-pip python3-pytest build-essential \
      libicu70 libssl3 libkrb5-3 zlib1g liblttng-ust1 libxml2 libunwind8 libcurl4 \
      libgtk-3-0 libwebkit2gtk-4.0-37 libglu1-mesa libnss3 libxss1 libasound2 libgbm1 libsecret-1-0 \
      xvfb xauth x11vnc fluxbox dbus-x11 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -s /bin/bash runner

# ── Слой 2: Temurin JDK 17 (эталон CI, Tycho release=17) ─────────────────────────────────
# Adoptium API отдаёт последний GA JDK 17; на живом раннере это 17.0.21.1.
# Ставить именно 17, не 25: Tycho/OSGi-сборка SI-MCP собрана под JavaSE-17.
RUN curl -fsSL -o /tmp/jdk.tgz \
      "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse" \
 && mkdir -p /home/runner/jdk17 \
 && tar xzf /tmp/jdk.tgz -C /home/runner/jdk17 --strip-components=1 \
 && rm -f /tmp/jdk.tgz \
 && chown -R runner:runner /home/runner/jdk17

# ── Слой 3: Maven 3.9.9 + путь /opt/apache-maven-3.9.9 ───────────────────────────────────
# Не косметика: workflow `сервер-тесты.yml` жёстко вызывает /opt/apache-maven-3.9.9/bin/mvn.
RUN curl -fsSL -o /tmp/mvn.tgz \
      "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
 && mkdir -p /home/runner/maven \
 && tar xzf /tmp/mvn.tgz -C /home/runner/maven --strip-components=1 \
 && rm -f /tmp/mvn.tgz \
 && ln -sfn /home/runner/maven /opt/apache-maven-3.9.9 \
 && chown -R runner:runner /home/runner/maven

# ── Слой 4: gh CLI ───────────────────────────────────────────────────────────────────────
# Нужен релизному `снимок.yml` (`gh release`); на живом раннере отсутствовал (§3).
RUN curl -fsSL -o /tmp/gh.tgz \
      "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" \
 && tar xzf /tmp/gh.tgz -C /tmp \
 && install -m 0755 "/tmp/gh_${GH_VERSION}_linux_amd64/bin/gh" /usr/local/bin/gh \
 && rm -rf "/tmp/gh_${GH_VERSION}_linux_amd64" /tmp/gh.tgz

# ── Слой 5: шимы /usr/local/bin (то же содержимое, что на живом раннере) ─────────────────
COPY bin/mvn      /usr/local/bin/mvn
COPY bin/pytest   /usr/local/bin/pytest
RUN chmod 0755 /usr/local/bin/mvn /usr/local/bin/pytest \
 && ln -sfn /home/runner/jdk17/bin/java  /usr/local/bin/java \
 && ln -sfn /home/runner/jdk17/bin/javac /usr/local/bin/javac \
 && ln -sfn /usr/bin/pip3               /usr/local/bin/pip3

# ── Слой 6: actions-runner 2.338.2 ───────────────────────────────────────────────────────
# Регистрация (.runner/.credentials) в образ НЕ входит — это секрет. Она монтируется из хоста,
# см. README.md. Без неё entrypoint уходит в `sleep infinity` (тот же контракт, что у текущего образа).
RUN mkdir -p /home/runner/actions-runner \
 && curl -fsSL -o /tmp/runner.tgz \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
 && tar xzf /tmp/runner.tgz -C /home/runner/actions-runner \
 && rm -f /tmp/runner.tgz \
 && /home/runner/actions-runner/bin/installdependencies.sh \
 && chown -R runner:runner /home/runner/actions-runner

# ── Слой 7: 1С:EDT и платформа (большие/лицензионные — только из локального контекста) ────
# В контейнере лежат УСТАНОВЛЕННЫЕ деревья, а не установщики: /opt/si-edt (components, products,
# common) и /opt/1cv8 (conf, x86_64). Замер 26.11.2026: то, что осталось в /home/runner от сборки
# (edt.tar.gz, platform.zip), — это ОФФЛАЙН-УСТАНОВЩИКИ (.dar/.car и setup-full-*.run), а не готовые
# каталоги; поэтому в образ кладём снимки установленных деревьев, а не установщики — так сборка
# детерминирована и не зависит от недокументированных ключей .run.
# Архивы НЕ в git (.gitignore), снимаются с живого контейнера ДО его чистки — см. README.md.
#   si-edt.tar.gz = содержимое /opt/si-edt     · 1cv8.tar.gz = содержимое /opt/1cv8
ADD si-edt.tar.gz /opt/si-edt/
ADD 1cv8.tar.gz   /opt/1cv8/
RUN chmod -R a+rX /opt/si-edt /opt/1cv8

# ── Слой 8: точка входа ──────────────────────────────────────────────────────────────────
COPY bin/si1c-entrypoint /usr/local/bin/si1c-entrypoint
RUN chmod 0755 /usr/local/bin/si1c-entrypoint

ENTRYPOINT ["/usr/local/bin/si1c-entrypoint"]
CMD ["/bin/bash"]