export function normalizeChatMarkdown(text: string): string {
  let fence = "";
  return text.replace(/\r\n?/g, "\n").split("\n").map(line => {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (marker) {
      if (!fence) fence = marker[1];
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = "";
      return line;
    }
    if (fence) return line;

    // Older answers sometimes put Unicode bullets and numbered bold lead-ins on one line.
    return line.split(/(`+[^`]*`+)/g).map((part, index) => {
      if (index % 2) return part;
      const bullets = part
        .replace(/^([ \t]*)[•●▪][ \t]*/, "$1- ")
        .replace(/[ \t]*[•●▪][ \t]*(?=\S)/g, "\n- ");
      const numbers = [...bullets.matchAll(/(?:^|[ \t])(\d+)[.)][ \t]+(?=\*\*)/g)];
      if (numbers.length < 2 || !numbers.every((match, i) => !i || Number(match[1]) === Number(numbers[i - 1][1]) + 1)) return bullets;
      return bullets.replace(/(?:^|[ \t])(\d+)[.)][ \t]+(?=\*\*)/g, "\n$1. ");
    }).join("");
  }).join("\n").trim();
}
