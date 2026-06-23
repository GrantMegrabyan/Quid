import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		alias: {
			$components: 'src/lib/components',
			$repos: 'src/lib/repos',
			$types: 'src/lib/types',
			$utils: 'src/lib/utils'
		},
		// adapter-node builds a standalone Node server (`node build`) for the Docker image.
		// See https://svelte.dev/docs/kit/adapter-node for more information.
		adapter: adapter()
	}
};

export default config;
