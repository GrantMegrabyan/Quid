export const UNCATEGORIZED_COLOR = '#9ca3af' as const;

const SATURATION = 68;
const LIGHTNESS = 52;

function hashString(value: string): number {
	let hash = 0;
	for (let i = 0; i < value.length; i += 1) {
		hash = ((hash * 31) + value.charCodeAt(i)) >>> 0;
	}
	return hash;
}

function normalizeHue(value: number): number {
	return ((value % 360) + 360) % 360;
}

export function hslToHex(h: number, s: number, l: number): string {
	const hue = normalizeHue(h);
	const saturation = Math.max(0, Math.min(100, s)) / 100;
	const lightness = Math.max(0, Math.min(100, l)) / 100;

	const chroma = (1 - Math.abs((2 * lightness) - 1)) * saturation;
	const hPrime = hue / 60;
	const x = chroma * (1 - Math.abs((hPrime % 2) - 1));

	let r1 = 0;
	let g1 = 0;
	let b1 = 0;

	if (hPrime >= 0 && hPrime < 1) {
		r1 = chroma;
		g1 = x;
	} else if (hPrime < 2) {
		r1 = x;
		g1 = chroma;
	} else if (hPrime < 3) {
		g1 = chroma;
		b1 = x;
	} else if (hPrime < 4) {
		g1 = x;
		b1 = chroma;
	} else if (hPrime < 5) {
		r1 = x;
		b1 = chroma;
	} else {
		r1 = chroma;
		b1 = x;
	}

	const match = lightness - (chroma / 2);
	const toHex = (channel: number) => {
		const value = Math.round((channel + match) * 255);
		return value.toString(16).padStart(2, '0');
	};

	return `#${toHex(r1)}${toHex(g1)}${toHex(b1)}`;
}

export function colorForCategoryId(id: string): string {
	if (id.trim().toLowerCase() === 'uncategorized') {
		return UNCATEGORIZED_COLOR;
	}

	const hue = hashString(id) % 360;
	return hslToHex(hue, SATURATION, LIGHTNESS).toLowerCase();
}
