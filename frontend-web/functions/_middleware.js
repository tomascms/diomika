/**
 * Block sensitive path probes on Cloudflare Pages (SPA otherwise returns index.html).
 */
const BLOCK = [
  /^\/\.env(?:$|\.)/i,
  /^\/\.git(?:$|\/)/i,
  /^\/package(?:-lock)?\.json$/i,
  /^\/vite\.config\./i,
  /^\/src(?:$|\/)/i,
  /^\/backend-api(?:$|\/)/i,
  /^\/\.github(?:$|\/)/i,
  /^\/node_modules(?:$|\/)/i,
];

// Domínio canónico: diomika.com (sem www) → https://www.diomika.com, mesmo caminho.
const CANONICAL_HOST = "www.diomika.com";
const REDIRECT_HOSTS = new Set(["diomika.com"]);

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (REDIRECT_HOSTS.has(url.hostname)) {
    url.hostname = CANONICAL_HOST;
    url.protocol = "https:";
    return Response.redirect(url.toString(), 301);
  }
  const path = url.pathname;
  if (BLOCK.some((re) => re.test(path))) {
    return new Response("Not Found", {
      status: 404,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  }
  return context.next();
}
