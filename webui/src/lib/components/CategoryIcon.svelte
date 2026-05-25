<script lang="ts">
	import { getCategoryIconComponent, normalizeCategoryIcon } from '$utils/categoryIcons';

	let {
		name,
		size = 18,
		strokeWidth = 2.25
	}: { name?: string; size?: number; strokeWidth?: number } = $props();

	const iconName = $derived(normalizeCategoryIcon(name));
	const Icon = $derived(getCategoryIconComponent(iconName));
</script>

<Icon {size} {strokeWidth} aria-hidden="true" />
