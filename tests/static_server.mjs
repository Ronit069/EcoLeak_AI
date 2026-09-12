import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root = process.argv[2], port = Number(process.argv[3]);
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml' };
http.createServer((req, res) => {
  const urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  // API paths: NEVER return index.html (explicit 404 so live calls fail loudly).
  // /mocks/* are real static files (dist copies) used by the frontend's
  // per-group mock fallback — they must be served, not blocked.
  if (urlPath.startsWith('/api/')) {
    res.writeHead(404, { 'content-type': 'application/json' });
    return res.end('{"error_code":"NOT_FOUND","message":"static server has no API","severity":"ERROR","details":{}}');
  }
  let f = path.join(root, urlPath === '/' ? 'index.html' : urlPath);
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(root, 'index.html');
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
}).listen(port, () => console.log(`static ${root} on ${port}`));
