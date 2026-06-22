import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const API_PORT = 8001;
const API_URL = `http://localhost:${API_PORT}`;
const TEST_DB_PATH = resolve(here, '..', 'api', '.data', 'quid-e2e.db');
const TEST_DATABASE_URL = `sqlite+aiosqlite:///${TEST_DB_PATH}`;
const API_DIR = resolve(here, '..', 'api');
// Shared secret the e2e harness sends on every /api/v1/testing/* request.
const TESTING_TOKEN = 'e2e-testing-token';

export default defineConfig({
	webServer: [
		{
			command: `rm -f "${TEST_DB_PATH}" && uv run quid-api migrate && uv run quid-api serve --port ${API_PORT} --log-level warning`,
			cwd: API_DIR,
			url: `${API_URL}/health`,
			reuseExistingServer: false,
			timeout: 60_000,
			env: {
				QUID_DATABASE_URL: TEST_DATABASE_URL,
				QUID_TESTING: '1',
				QUID_TESTING_TOKEN: TESTING_TOKEN
			}
		},
		{
			command: 'npm run build && npm run preview -- --port 4173 --strictPort',
			port: 4173,
			reuseExistingServer: false,
			timeout: 120_000,
			env: {
				PUBLIC_API_BASE_URL: API_URL
			}
		}
	],
	use: {
		baseURL: 'http://localhost:4173'
	},
	workers: 1,
	testMatch: '**/*.e2e.{ts,js}'
});
