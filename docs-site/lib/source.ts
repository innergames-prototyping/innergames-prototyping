import path from 'node:path';
import { llms, loader } from 'fumadocs-core/source';
import { docsRoute } from './shared';
import { defineDocs } from 'fumadocs-mdx/macro';
import { metaSchema, pageSchema } from 'fumadocs-core/source/schema';

const docs = defineDocs({
  dir: '../Documentation',
  docs: {
    // the Markdown files have no frontmatter: fall back to their first heading
    schema: (ctx) =>
      pageSchema.extend({
        title: pageSchema.shape.title.default(
          /^#\s+(.+)$/m.exec(ctx.source)?.[1] ?? path.basename(ctx.path, path.extname(ctx.path)),
        ),
      }),
    postprocess: {
      includeProcessedMarkdown: true,
    },
  },
  meta: {
    schema: metaSchema,
  },
});

// See https://fumadocs.dev/docs/headless/source-api for more info
export const source = loader({
  baseUrl: docsRoute,
  source: docs.toFumadocsSource(),
  plugins: [],
});

export const docsLlms = llms(source, {
  renderPage: async (page) => `# ${page.data.title} (${page.url})

${await page.data.getText('processed')}`,
});
