# docs-site

Static documentation site built with [Fumadocs](https://fumadocs.dev). Every Markdown file in
[`../docs`](../docs) becomes a page; the first heading is used as its title.

## Develop

```bash
npm install
npm run dev
```

`npm run build` writes the static site to `out/`.

## Deploy (Dokploy)

Create an application from this repository with build type **Dockerfile**:

| Setting             | Value                  |
| ------------------- | ---------------------- |
| Docker File         | `docs-site/Dockerfile` |
| Docker Context Path | `.`                    |
| Container port      | `80`                   |

The image builds the site and serves it with nginx.
