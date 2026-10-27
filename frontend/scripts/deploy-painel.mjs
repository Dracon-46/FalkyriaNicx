// Publica dist-painel/ no branch gh-pages do repositório nicx-painel, que o
// GitHub Pages serve em https://dracon-46.github.io/nicx-painel/.
// Uso: npm run deploy:painel (gera o build antes).
import { execFileSync } from 'node:child_process';
import { existsSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const dist = join(process.cwd(), 'dist-painel');
if (!existsSync(join(dist, 'index.html'))) {
  console.error('dist-painel/index.html não existe: rode npm run build:painel.');
  process.exit(1);
}
const origin = 'https://github.com/Dracon-46/nicx-painel.git';
const git = (...args) => execFileSync('git', args, { cwd: dist, stdio: 'inherit' });

// Sem isso o Pages roda o Jekyll e descarta arquivos que começam com "_".
writeFileSync(join(dist, '.nojekyll'), '');
rmSync(join(dist, '.git'), { recursive: true, force: true });
git('init', '-q', '-b', 'gh-pages');
git('add', '-A');
// Sempre na conta pessoal, qualquer que seja o git config da máquina.
git('-c', 'user.name=Arthur G. Camzano', '-c', 'user.email=arthurgaspare@gmail.com',
  'commit', '-q', '-m', 'Publicar Painel Falkyria');
// Envia com o login da Dracon-46 sem trocar a conta ativa do gh.
git('-c', 'credential.helper=',
  '-c', 'credential.helper=!f() { echo username=Dracon-46; echo "password=$(gh auth token --user Dracon-46)"; }; f',
  'push', '-q', '-f', origin, 'gh-pages');
rmSync(join(dist, '.git'), { recursive: true, force: true });
console.log('Painel publicado: https://dracon-46.github.io/nicx-painel/');
