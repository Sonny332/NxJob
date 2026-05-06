export type PageContext = {
  url: string;
  title: string;
  selectedText: string;
  pageTextExcerpt: string;
};

const MAX_TEXT_EXCERPT = 12000;

export function capturePageContext(): PageContext {
  const selectedText = window.getSelection()?.toString().trim() ?? "";
  const pageText = document.body?.innerText.trim() ?? "";

  return {
    url: window.location.href,
    title: document.title,
    selectedText,
    pageTextExcerpt: pageText.slice(0, MAX_TEXT_EXCERPT)
  };
}

