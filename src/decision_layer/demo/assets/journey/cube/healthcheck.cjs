const { createHmac } = require('node:crypto');

const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
const payload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 })).toString('base64url');
const signature = createHmac('sha256', process.env.CUBEJS_API_SECRET)
  .update(`${header}.${payload}`).digest('base64url');

fetch('http://127.0.0.1:4000/cubejs-api/v1/meta', {
  headers: { Authorization: `${header}.${payload}.${signature}` },
  signal: AbortSignal.timeout(4000),
}).then(async response => {
  if (!response.ok || !(await response.json()).cubes?.length) process.exit(1);
}).catch(() => process.exit(1));
