# Builds the static Observable Framework site. `observable build` runs the
# .json.py data loaders as part of the build, so this image needs Python
# alongside Node — not just a JS toolchain.
#
# Expects data/books.jsonl to be available at /data/books.jsonl at build
# time (see docker-compose.yml: the scraper's scraper-data volume is mounted
# there). The three-levels-up path in src/data/*.json.py
# (dirname(__file__)/../../../data/books.jsonl) resolves to exactly /data
# when this image's project root is /app, so no path changes were needed in
# the loaders themselves.
FROM node:20-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install

COPY . .

# `observable build` rmdir's its output directory before writing to it,
# which fails if that directory is itself a volume mount point (its
# contents can be cleared, but the mount point can't be removed) — so build
# into the plain (unmounted) ./dist first, then publish into the volume
# mounted at /publish.
CMD ["sh", "-c", "npm run build && rm -rf /publish/* && cp -r dist/. /publish/"]
