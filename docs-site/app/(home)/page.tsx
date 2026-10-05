import Link from 'next/link';
import { source } from '@/lib/source';
import { appName } from '@/lib/shared';

export default function HomePage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold">{appName}</h1>
      <ul className="flex flex-col gap-2">
        {source.getPages().map((page) => (
          <li key={page.url}>
            <Link href={page.url} className="font-medium underline">
              {page.data.title}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
