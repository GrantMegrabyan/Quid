import type { AppSettings, AppSettingsUpdate } from '$types';
import { httpClient, HttpClient } from './httpClient.js';
import type { AppSettingsRepository } from './types.js';

export class HttpAppSettingsRepository implements AppSettingsRepository {
	constructor(private readonly client: HttpClient = httpClient) {}

	async get(): Promise<AppSettings> {
		return this.client.request<AppSettings>('api/v1/settings');
	}

	async update(patch: AppSettingsUpdate): Promise<AppSettings> {
		return this.client.request<AppSettings>('api/v1/settings', {
			method: 'PATCH',
			body: patch
		});
	}
}

export const httpAppSettingsRepository: AppSettingsRepository = new HttpAppSettingsRepository();
