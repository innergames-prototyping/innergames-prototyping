import path from 'node:path';
import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  // emit /page/index.html so a plain static file server needs no rewrite rules
  trailingSlash: true,
  reactStrictMode: true,
  // content lives in ../docs, outside this app
  turbopack: { root: path.join(import.meta.dirname, '..') },
};

export default withMDX(config);
