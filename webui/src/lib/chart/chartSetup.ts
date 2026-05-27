import { Chart, registerables } from 'chart.js';

let registered = false;

export function ensureChartJsRegistered() {
	if (registered) return;

	Chart.register(...registerables);
	registered = true;
}

export function chartThemeColors() {
	const s = getComputedStyle(document.documentElement);
	const get = (v: string) => s.getPropertyValue(v).trim();
	return {
		tick: get('--ctp-subtext0') || '#a6adc8',
		grid: get('--ctp-surface1') || '#45475a',
		legend: get('--ctp-subtext0') || '#a6adc8'
	};
}
