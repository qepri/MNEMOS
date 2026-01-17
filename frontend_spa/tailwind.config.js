/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/**/*.{html,ts}",
    ],
    theme: {
        extend: {
            colors: {
                base: 'var(--color-base)',
                'base-subtle': 'var(--color-base-subtle)',
                sidebar: 'var(--color-sidebar)',
                panel: 'var(--color-panel)',
                input: 'var(--color-input)',
                hover: 'var(--color-hover)',
                divider: 'var(--color-divider)',

                primary: 'var(--color-primary)',
                secondary: 'var(--color-secondary)',

                accent: 'var(--color-accent)',
                'accent-dark': 'var(--color-accent-dark)',
                'accent-subtle': 'var(--color-accent-subtle)',

                success: 'var(--color-success)',
                warning: 'var(--color-warning)',
                error: 'var(--color-error)',
            }
        },
    },
    plugins: [
        require('daisyui'),
    ],
    daisyui: {
        themes: [], // Empty array = no DaisyUI themes, we use our own CSS variables
        base: false, // Disable DaisyUI base styles
        styled: false, // Disable DaisyUI styled components
    },
}
