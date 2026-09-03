/**
 * A message worth showing the reader.
 *
 * FastAPI returns three different shapes: a plain string for a raised
 * HTTPException, a list of field errors for a validation failure, and no body
 * at all for an unhandled 500. Treating them alike produced "[object Object]"
 * or an unhelpful generic, which hides the one detail that would explain the
 * problem.
 */
export const describeError = (err: any, fallback = 'Something went wrong.'): string => {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : null;
    const msg = first?.msg ?? 'is not valid';
    return field ? `${String(field)}: ${msg}` : String(msg);
  }

  if (err?.code === 'ERR_NETWORK' || !err?.response) {
    return 'Cannot reach the server. Check that it is running and the address is right.';
  }

  if (status >= 500) {
    return `The server failed (HTTP ${status}). Check its logs: docker logs performance-backend`;
  }
  if (status) return `${fallback} (HTTP ${status})`;
  return fallback;
};
