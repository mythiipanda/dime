// Type definitions for Next.js pages
export type SearchParams = {
  [key: string]: string | string[] | undefined;
};

export type PageProps = {
  params?: { [key: string]: string };
  searchParams?: SearchParams;
}; 