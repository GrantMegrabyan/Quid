import { RepositoryError, type RepositoryErrorCode } from './types.js';

const REPOSITORY_ERROR_CODES: ReadonlySet<RepositoryErrorCode> = new Set([
	'NOT_FOUND',
	'IMMUTABLE',
	'VALIDATION'
]);

interface ErrorBody {
	code?: unknown;
	message?: unknown;
}

function defaultBaseUrl(): string {
	const env = (import.meta.env ?? {}) as Record<string, string | undefined>;
	return env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000';
}

function isErrorBody(value: unknown): value is ErrorBody {
	return typeof value === 'object' && value !== null;
}

function toRepositoryError(status: number, body: unknown): RepositoryError {
	if (isErrorBody(body) && typeof body.code === 'string' && typeof body.message === 'string') {
		if (REPOSITORY_ERROR_CODES.has(body.code as RepositoryErrorCode)) {
			return new RepositoryError(body.code as RepositoryErrorCode, body.message);
		}
		return new RepositoryError('VALIDATION', body.message);
	}
	if (status === 404) {
		return new RepositoryError('NOT_FOUND', `Not found (HTTP ${status}).`);
	}
	if (status === 409) {
		return new RepositoryError('IMMUTABLE', `Conflict (HTTP ${status}).`);
	}
	return new RepositoryError('VALIDATION', `Request failed (HTTP ${status}).`);
}

interface RequestOptions {
	method?: string;
	body?: unknown;
	formData?: FormData;
	query?: Record<string, string | number | undefined>;
}

export class HttpClient {
	constructor(private readonly baseUrl: string = defaultBaseUrl()) {}

	async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
		const url = new URL(path, this.baseUrl.endsWith('/') ? this.baseUrl : this.baseUrl + '/');
		if (options.query) {
			for (const [k, v] of Object.entries(options.query)) {
				if (v !== undefined) {
					url.searchParams.set(k, String(v));
				}
			}
		}

		let headers: Record<string, string> | undefined;
		let body: BodyInit | undefined;
		if (options.formData !== undefined) {
			body = options.formData;
		} else if (options.body !== undefined) {
			headers = { 'Content-Type': 'application/json' };
			body = JSON.stringify(options.body);
		}

		const init: RequestInit = {
			method: options.method ?? 'GET',
			headers,
			body
		};

		let response: Response;
		try {
			response = await fetch(url.toString(), init);
		} catch (cause) {
			throw new RepositoryError('VALIDATION', `Network error: ${(cause as Error).message}`);
		}

		if (response.status === 204) {
			return undefined as T;
		}

		const text = await response.text();
		const parsed: unknown = text ? JSON.parse(text) : undefined;

		if (!response.ok) {
			throw toRepositoryError(response.status, parsed);
		}

		return parsed as T;
	}
}

export const httpClient = new HttpClient();
