import {spawn} from 'node:child_process';

const url = 'http://127.0.0.1:5174';
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

export default async function startVite() {
  const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1'], {
    cwd: process.cwd(),
    env: {...process.env, VITE_P11_RESOURCES: 'all'},
    stdio: 'ignore',
    windowsHide: true,
  });
  let stopped = false;
  server.once('exit', () => { stopped = true; });
  const stop = async () => {
    if (stopped) return;
    const exit = new Promise(resolve => server.once('exit', resolve));
    server.kill('SIGTERM');
    const closed = await Promise.race([exit.then(() => true), wait(3000).then(() => false)]);
    if (!closed && !stopped) {
      server.kill('SIGKILL');
      await Promise.race([exit, wait(3000)]);
    }
    if (!stopped) throw new Error('Vite de teste não encerrou após SIGTERM/SIGKILL.');
  };
  try {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (stopped) throw new Error(`Vite encerrou durante a inicialização (código ${server.exitCode}).`);
      try {
        const response = await fetch(url, {signal: AbortSignal.timeout(500)});
        if (response.ok) {
          await response.body?.cancel();
          return stop;
        }
      } catch (error) {
        if (stopped) throw error;
      }
      await wait(100);
    }
    throw new Error('Vite não ficou pronto em 10 segundos.');
  } catch (error) {
    await stop().catch(() => {});
    throw error;
  }
}
