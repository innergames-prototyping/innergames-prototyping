# Build context is the repository root: the content lives in ../Documentation.
FROM node:24-alpine AS build
WORKDIR /repo/docs-site
COPY docs-site/package.json docs-site/package-lock.json ./
RUN npm ci
COPY Documentation /repo/Documentation
COPY docs-site ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /repo/docs-site/out /usr/share/nginx/html
EXPOSE 80
