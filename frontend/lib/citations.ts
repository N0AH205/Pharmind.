export interface CitationSource {
  id: string;
  num: number;
  name: string;
  url: string;
  text?: string;
}

export function normalizeChatCitations<T extends CitationSource>(rawText: string, initialSources: T[] = []) {
  const sources = initialSources.filter((source, index) =>
    Number.isInteger(source.num) && source.num > 0 && initialSources.findIndex(item => item.num === source.num) === index,
  ).map(source => ({ ...source, url: /^(https?:\/\/|\/api\/documents\/)/i.test(source.url || "") ? source.url : "" }));
  const text = rawText.replace(/\[((?:SOURCE_)?\d+(?:\s*,\s*(?:SOURCE_)?\d+)*)\](?:\([^)]*\))?/gi, (_, labels: string) => {
    const numbers = labels.split(/\s*,\s*/).flatMap(label => {
      const source = label.toUpperCase().startsWith("SOURCE_")
        ? sources.find(item => item.id.toUpperCase() === label.toUpperCase())
        : sources.find(item => item.num === Number(label));
      return source ? [source.num] : [];
    });
    return numbers.length ? `[${[...new Set(numbers)].join(", ")}]` : "";
  });
  return { text, sources };
}
