// Lets code outside the React tree (the global QueryClient error handler in main.tsx) trigger an
// SPA navigation. react-router's plain <BrowserRouter> doesn't expose its navigate function
// outside components, so <NavigateBridge> (rendered once near the app root, see App.tsx) hands
// its own useNavigate() result to setNavigate(); anything registered here runs before that (there
// is none in practice) falls back to a full page load.

type NavigateFn = (path: string, options?: { replace?: boolean }) => void;

let navigateImpl: NavigateFn | null = null;

export function setNavigate(fn: NavigateFn): void {
  navigateImpl = fn;
}

export function navigateTo(path: string, options?: { replace?: boolean }): void {
  if (navigateImpl) {
    navigateImpl(path, options);
  } else {
    window.location.assign(path);
  }
}
