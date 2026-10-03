export function LoadingIndicator() {
  return <span className="dl-loading" aria-hidden="true">{Array.from({ length: 8 }, (_, index) => <i key={index} />)}</span>;
}
