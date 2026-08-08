const CODE_MESSAGES = {
  INVALID_URL: "The URL you entered is not valid. Please enter a full http:// or https:// URL.",
  SSRF_BLOCKED: "That URL points to a private or internal address and cannot be scraped.",
  ROBOTS_DISALLOWED: "The target site's robots.txt disallows scraping this URL.",
  CONTENT_TYPE_UNSUPPORTED: "The URL did not return an HTML page (e.g. it returned a PDF or image).",
  RESPONSE_TOO_LARGE: "The page is too large to process.",
  TIMEOUT: "The request timed out. The target site may be slow or unreachable.",
  UPSTREAM_HTTP_ERROR: "The target site returned an error or too many redirects.",
  RATE_LIMITED: "You've made too many requests. Please wait a moment and try again.",
  PARSE_ERROR: "The page could not be parsed.",
  VALIDATION_ERROR: "The request was invalid.",
  INTERNAL_ERROR: "Something went wrong on our end. Please try again.",
  SERVICE_UNAVAILABLE: "The extraction service is unreachable. Please try again shortly.",
};

export default function ErrorMessage({ error, isServiceUnavailable = false }) {
  if (isServiceUnavailable) {
    return (
      <div role="alert" className="rounded-md bg-yellow-50 border border-yellow-200 p-4 text-yellow-800 text-sm">
        {CODE_MESSAGES.SERVICE_UNAVAILABLE}
      </div>
    );
  }

  if (!error) return null;

  const code = error?.code ?? "INTERNAL_ERROR";
  const message = CODE_MESSAGES[code] ?? CODE_MESSAGES.INTERNAL_ERROR;

  return (
    <div role="alert" className="rounded-md bg-red-50 border border-red-200 p-4 text-red-800 text-sm">
      <p className="font-medium">{message}</p>
      {import.meta.env.DEV && error.message && (
        <p className="mt-1 text-xs text-red-600 font-mono">{error.message}</p>
      )}
    </div>
  );
}
