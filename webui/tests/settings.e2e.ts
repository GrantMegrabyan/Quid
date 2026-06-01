import { expect, test } from '@playwright/test';
import { buildSeed, seedApiState } from './helpers.js';

test.describe('settings page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, buildSeed());
	});

	test('AI toggles render and default on', async ({ page }) => {
		await page.goto('/settings');

		await expect(page.getByTestId('settings-categorize-model-input')).toBeVisible();
		await expect(page.getByTestId('settings-ai-categorize-toggle')).toBeVisible();
		await expect(page.getByTestId('settings-ai-short-names-toggle')).toBeVisible();
		await expect(page.getByTestId('settings-categorize-model-input')).toHaveValue('google/gemini-2.5-flash');
		await expect(page.getByTestId('settings-ai-categorize-toggle')).toBeChecked();
		await expect(page.getByTestId('settings-ai-short-names-toggle')).toBeChecked();
	});

	test('categorisation model accepts any model id and persists across reload', async ({ page }) => {
		await page.goto('/settings');

		// A free-form model id that is NOT one of the suggested options, to prove
		// the text box accepts arbitrary OpenRouter models.
		const customModel = 'anthropic/claude-haiku-4.5';
		const input = page.getByTestId('settings-categorize-model-input');
		await input.fill(customModel);

		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();

		await page.reload();
		await expect(page.getByTestId('settings-categorize-model-input')).toHaveValue(customModel);
	});

	test('AI categorisation toggle persists across reload', async ({ page }) => {
		await page.goto('/settings');

		const toggle = page.getByTestId('settings-ai-categorize-toggle');
		if (await toggle.isChecked()) {
			await toggle.uncheck();
		} else {
			await toggle.check();
		}

		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();

		const expectedChecked = await toggle.isChecked();
		await page.reload();
		if (expectedChecked) {
			await expect(page.getByTestId('settings-ai-categorize-toggle')).toBeChecked();
		} else {
			await expect(page.getByTestId('settings-ai-categorize-toggle')).not.toBeChecked();
		}
	});

	test('AI short names toggle persists across reload', async ({ page }) => {
		await page.goto('/settings');

		const toggle = page.getByTestId('settings-ai-short-names-toggle');
		if (await toggle.isChecked()) {
			await toggle.uncheck();
		} else {
			await toggle.check();
		}

		await page.getByTestId('settings-save-button').click();
		await expect(page.getByTestId('settings-message')).toBeVisible();

		const expectedChecked = await toggle.isChecked();
		await page.reload();
		if (expectedChecked) {
			await expect(page.getByTestId('settings-ai-short-names-toggle')).toBeChecked();
		} else {
			await expect(page.getByTestId('settings-ai-short-names-toggle')).not.toBeChecked();
		}
	});
});
