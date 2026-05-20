import { Chart, registerables } from 'chart.js';

let registered = false;

export function ensureChartJsRegistered() {
	if (registered) return;

	Chart.register(...registerables);
	registered = true;
}

export function chartThemeColors(isDark: boolean) {
	if (isDark) {
		return {
			tick: '#d1d5db',
			grid: '#374151',
			legend: '#d1d5db'
		};
	}

	return {
		tick: '#374151',
		grid: '#e5e7eb',
		legend: '#374151'
	};
}
