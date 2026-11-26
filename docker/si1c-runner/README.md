# Self-hosted runner image `si1c-runner` (container `si1c-ci`)

Recipe: [`Dockerfile`](./Dockerfile) + [`bin/`](./bin). Задача
[Lavren73/SI-MCP#640](https://github.com/Lavren73/SI-MCP/issues/640) §5 «закрепить в образе».

## Зачем это

До 26.11.2026 образ `si1c-runner:local` не имел рецепта: контейнер `si1c-ci` собирался 2026-11-10,
после чего правился руками (`docker commit`). Любое пересоздание контейнера теряло JDK 17, Maven,
шимы `/usr/local/bin` и (отсутствовавший) `gh`. Теперь всё это — текст в этом каталоге.

## Что воспроизводится ([ИЗМЕРЕНО] на живом контейнере 26.11.2026)

| Слой | Состав |
|---|---|
| база | Ubuntu 22.04.5, `python3` 3.10.12, `gosu`, `procps`, `build-essential` 12.9ubuntu3 |
| python | `python3-pytest` 6.2.5, `python3-pip` 22.0.2 (`pytest` = `python3 -m pytest`) |
| GUI-стек | `xvfb` 2:21.1.4, `xauth`, `x11vnc`, `fluxbox`, `dbus-x11`, GTK3 + `libwebkit2gtk-4.0-37` 2.50.4 |
| Java | Temurin **JDK 17.0.21.1** → `/home/runner/jdk17` (319M) — Tycho `release=17` |
| Maven | **3.9.9** → `/home/runner/maven` + симлинк `/opt/apache-maven-3.9.9` (жёстко ждёт `сервер-тесты.yml`) |
| gh | **2.106.0** → `/usr/local/bin/gh` (нужен релизному `снимок.yml`, `gh release`) |
| раннер | `actions-runner` **2.338.2**, agentName `si1c-docker`, agentId 22 |
| 1С | `/opt/si-edt` 7.6G (EDT 2026.2 + Axiom JDK 25), `/opt/1cv8` 2.7G (8.3.27.2342) |

Не входит в образ осознанно: `/home/runner/.m2` (1.3G, кэш — регенерируется), `_work` (рабочие
каталоги джобов), `.runner`/`.credentials` (секрет регистрации), `.1cv8/…/*.lic` (лицензия 1С).

## Забрать нужное ПЕРЕД чисткой контейнера

Всё, что не воспроизводится из сети, снимается с ЖИВОГО контейнера **до** удаления
`edt.tar.gz`/`platform.zip` и до пересоздания. На хосте `odin`:

```bash
mkdir -p ~/si1c-runner-context ~/si1c-runner-state && chmod 700 ~/si1c-runner-state

# 1. Установленные деревья EDT и платформы (сырьё для слоя 7). ~2.5–4 GB каждое после сжатия.
docker exec si1c-ci tar czf - -C /opt si-edt > ~/si1c-runner-context/si-edt.tar.gz
docker exec si1c-ci tar czf - -C /opt 1cv8   > ~/si1c-runner-context/1cv8.tar.gz

# 2. Регистрация раннера — СЕКРЕТ, в git не попадает, только в state-каталог хоста.
docker cp si1c-ci:/home/runner/actions-runner/.runner      ~/si1c-runner-state/.runner
docker cp si1c-ci:/home/runner/actions-runner/.credentials ~/si1c-runner-state/.credentials
chmod 600 ~/si1c-runner-state/.runner ~/si1c-runner-state/.credentials

# 3. Лицензия 1С (программная, привязана к железу хоста).
docker cp si1c-ci:/home/runner/.1cv8 ~/si1c-runner-state/.1cv8
```

Проверка целостности снимков до чистки: `tar tzf ~/si1c-runner-context/si-edt.tar.gz | head`
(ожидается `components/`, `products/`, `common/`), `tar tzf …/1cv8.tar.gz | head` (`conf/`, `x86_64/`).

## Сборка

```bash
cd docker/si1c-runner
ln -s ~/si1c-runner-context/si-edt.tar.gz .   # или скопировать рядом с Dockerfile
ln -s ~/si1c-runner-context/1cv8.tar.gz   .
docker build -t si1c-runner:local .
```

`[НЕ ПРОВЕРЕНО]` — образ по этому рецепту ещё **не собирался**. Сборка тяжёлая (слой EDT ~7.6G),
запускать её в объявленное окно работ, не во время джобов.

## Пересоздание контейнера с сохранением регистрации

```bash
docker stop si1c-ci && docker rename si1c-ci si1c-ci.old     # старый оставить до проверки
docker run -d --name si1c-ci --restart unless-stopped \
  -v ~/si1c-runner-state/.runner:/home/runner/actions-runner/.runner:ro \
  -v ~/si1c-runner-state/.credentials:/home/runner/actions-runner/.credentials:ro \
  -v ~/si1c-runner-state/.1cv8:/home/runner/.1cv8 \
  si1c-runner:local
```

Файловые bind-моунты именно на `.runner`/`.credentials` (а не на весь каталог
`actions-runner`) — иначе маскируются бинарники раннера.

## Мерка приёмки (из #640 §4)

```bash
docker exec si1c-ci bash -lc 'which java javac mvn pytest pip3 gh xvfb-run git'
docker exec si1c-ci java -version          # 17.0.21.1
docker exec si1c-ci mvn -v                 # Maven 3.9.9, home /opt/apache-maven-3.9.9
docker exec si1c-ci /opt/apache-maven-3.9.9/bin/mvn -v
docker exec si1c-ci pytest --version       # 6.2.5
docker exec si1c-ci gh --version           # 2.106.0
docker exec si1c-ci ls /opt/si-edt /opt/1cv8
```

Раннер должен снова появиться online в `Lavren73/SI-MCP` → Settings → Actions → Runners.
После успешной проверки старый контейнер `si1c-ci.old` удаляется отдельным решением владельца.

## Правила

- Секреты (`.runner`, `.credentials`, `*.lic`) — **никогда** в этот репозиторий и не в чат.
- Образ пересобирается только в объявленное окно; во время сборки джобы не запускаются.
- Правки рецепта — PR, не мержить (O-22), с пометками кто/когда/что/почему (#40).