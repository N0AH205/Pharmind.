export interface OllamaModel {
  name: string;
  can_chat: boolean | null;
}

export function selectedOllamaModel(models: OllamaModel[], selected: string) {
  return models.find(model => model.name === selected || model.name === `${selected}:latest`);
}

export function ollamaModelWarning(models: OllamaModel[], selected: string) {
  const model = selectedOllamaModel(models, selected);
  if (!models.length) return "Ollama is running, but no models are installed. Download an answer model, then refresh.";
  if (!models.some(item => item.can_chat !== false)) return "Only models that cannot generate answers were found. Download a text-generation model, then refresh.";
  if (!model) return `${selected || "The selected model"} is not installed. Choose an installed answer model.`;
  if (model.can_chat === false) return `${selected} cannot generate answers. Choose a text-generation model.`;
  return "";
}
