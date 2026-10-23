/**
 * Generic API types and error envelopes.
 */

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
  status?: number;
}

export interface PaginatedParams {
  limit?: number;
  offset?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
