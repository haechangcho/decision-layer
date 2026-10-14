export function isAssociation(value?: string | null): boolean {
  return value === "association" || value === "descriptive" || value === "associational";
}

export function supportsInterpretation(required: string, actual?: string | null): boolean {
  if (required === "descriptive") return true;
  if (required === "association") return isAssociation(actual);
  return required === actual;
}
