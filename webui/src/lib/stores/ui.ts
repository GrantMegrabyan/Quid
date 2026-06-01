import { currentMonthKey } from '$utils/dates';
import { persisted } from '$lib/stores/persisted';

const MONTH_KEY_RE = /^\d{4}-\d{2}$/;

/**
 * The month the user is currently viewing on the dashboard, persisted across
 * reloads so the app doesn't snap back to the current month after a refresh or
 * update. Defaults to the current month on first visit. A stored value that is
 * not a valid `YYYY-MM` key is ignored.
 */
export const selectedMonth = persisted<string>(
	'quid:selected-month:v1',
	currentMonthKey(),
	(value) => typeof value === 'string' && MONTH_KEY_RE.test(value)
);
