# Frontend architecture options

The current frontend is a static FastAPI-served app:

- `crd_notes/web/index.html` owns the page structure.
- `crd_notes/web/static/styles.css` owns all visual styling.
- `crd_notes/web/static/app.js` owns state, API calls, rendering, and events.
- `crd_notes/web/static/ui-copy.js` centralizes recurring Italian UI text.

This is no longer a single HTML monolith, but the JavaScript and page markup are still broad modules. The next architectural step should preserve the local-first startup path and avoid adding build complexity before the product needs it.

## Recommended next step

Move to native ES modules without a bundler:

- `api-client.js`: `fetch` wrapper and endpoint-specific calls.
- `state.js`: shared state, workspace selection, filter defaults.
- `render/`: one renderer per page area, for example `render/library.js`, `render/operations.js`, `render/settings.js`.
- `ui-copy.js`: labels, empty states, status messages, and repeated microcopy.
- `dom.js`: central element lookup and small DOM helpers.

Pros:

- Keeps the app install-free for users.
- Works with the existing FastAPI static file serving.
- Reduces the current `app.js` blast radius without forcing React/Vue/Svelte.
- Makes copy cleanup and responsive UI work easier to review.

Cons:

- No component compiler, no template type checks, and no automatic CSS scoping.
- More discipline is needed around module boundaries.
- Large interactive surfaces can still become hard to test if render functions keep growing.

## Alternative: HTMX plus server templates

Pros:

- Good fit for FastAPI and form-heavy workflows.
- Smaller client-side state for settings, filters, and CRUD operations.
- Progressive enhancement is straightforward.

Cons:

- Current UI does a lot of local rendering and polling, so migration would touch many flows.
- More backend template surface to test.
- Rich client behaviors such as the operations board still need custom JavaScript.

## Alternative: React or Preact with Vite

Pros:

- Strong component model for the current page sections.
- Better testability for stateful UI and conditional rendering.
- Easier long-term evolution if the app becomes a larger workspace product.

Cons:

- Adds Node build tooling to a mostly Python app.
- Packaging must include built assets and a clear dev/build workflow.
- More dependency surface for a local-first utility.

## Alternative: Svelte with Vite

Pros:

- Compact components and low runtime weight.
- Good fit for form-heavy, reactive UI.
- Less boilerplate than React for this scale.

Cons:

- Still adds a build step.
- Smaller ecosystem and fewer contributors may know it.
- Migration requires rewriting templates and event flows.

## Decision

For the next iteration, prefer native ES modules. It solves the immediate maintainability problem while keeping deployment simple. Reassess a compiled frontend only after the UI has several independently owned screens, browser-level tests, and enough repeated component logic to justify a build step.
