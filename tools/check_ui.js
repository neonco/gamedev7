/**
 * Проверка интерфейса без браузера: викторина, печать шпаргалки, QR на старте.
 *
 * Требует jsdom:
 *     npm install jsdom
 *     node tools/check_ui.js
 *
 * Проверяется то, что нельзя проверить статически: клики по вариантам,
 * подсчёт результата, раскрытие разборов, сброс, режим печати и сборка QR
 * из адреса страницы.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
const DOCS = path.join(ROOT, 'docs');
const problems = [];

function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) problems.push(`${name}: получил ${JSON.stringify(got)}, ожидал ${JSON.stringify(want)}`);
  console.log(`  ${ok ? 'ок ' : 'ПРОВАЛ'} ${name}`);
}

async function load(file) {
  const html = fs.readFileSync(path.join(DOCS, file), 'utf8');
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    resources: 'usable',
    url: 'file://' + path.join(DOCS, file),
    pretendToBeVisual: true,
  });
  await new Promise((resolve) => {
    if (dom.window.document.readyState === 'complete') resolve();
    else dom.window.addEventListener('load', resolve);
  });
  await new Promise((r) => setTimeout(r, 150));
  return dom;
}

const click = (dom, el) =>
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));

async function checkQuiz(dom) {
  const { document } = dom.window;
  const questions = Array.from(document.querySelectorAll('.quiz-q'));
  check('вопросы отрисованы', questions.length > 0, true);

  let expected = 0;
  questions.forEach((question, index) => {
    const options = Array.from(question.querySelectorAll('.opt'));
    check(
      `вопрос ${index + 1}: ровно один верный вариант`,
      options.filter((o) => o.dataset.ok === '1').length,
      1
    );
    const rightIndex = options.findIndex((opt) => opt.dataset.ok === '1');
    // в чётных вопросах отвечаем верно, в нечётных — заведомо мимо
    let pick = rightIndex;
    if (index % 2 === 1) pick = options.findIndex((opt) => opt.dataset.ok !== '1');
    else expected += 1;
    click(dom, options[pick]);
  });

  check('отмечены все вопросы', document.querySelectorAll('.opt.picked').length, questions.length);
  check(
    'разборы скрыты до проверки',
    Array.from(document.querySelectorAll('.quiz-explain')).filter((el) => el.hidden).length,
    questions.length
  );

  click(dom, document.querySelector('#quiz-check'));

  check(
    'счёт посчитан верно',
    document.querySelector('#quiz-score').textContent.trim(),
    `правильно ${expected} из ${questions.length}`
  );
  check('подсвечены верные ответы', document.querySelectorAll('.opt.good').length, questions.length);
  check('подсвечены ошибки', document.querySelectorAll('.opt.bad').length, questions.length - expected);
  check(
    'разборы раскрыты после проверки',
    Array.from(document.querySelectorAll('.quiz-explain')).filter((el) => el.hidden).length,
    0
  );
  check(
    'после проверки варианты заблокированы',
    Array.from(document.querySelectorAll('.opt')).filter((o) => o.disabled).length,
    questions.length * 3
  );

  click(dom, questions[0].querySelectorAll('.opt')[1]);
  check('после проверки выбор не меняется', questions[0].querySelectorAll('.opt.picked').length, 1);

  click(dom, document.querySelector('#quiz-reset'));
  check('сброс очищает отметки', document.querySelectorAll('.opt.picked, .opt.good, .opt.bad').length, 0);
  check('сброс очищает счёт', document.querySelector('#quiz-score').textContent.trim(), '');
  check(
    'сброс снимает блокировку',
    Array.from(document.querySelectorAll('.opt')).filter((o) => o.disabled).length,
    0
  );
}

async function checkPrint(dom) {
  const { document } = dom.window;
  const printBtn = document.querySelector('[data-print-cheat]');
  check('кнопка печати есть', !!printBtn, true);
  check('шпаргалка на месте', !!document.querySelector('.sec-cheat .cheat-body'), true);
  check('методичка свёрнута', document.querySelector('details.sec-teacher').open, false);
  click(dom, printBtn);
  check('на печать уходит только шпаргалка', document.body.classList.contains('print-cheat'), true);
}

/**
 * Стартовая страница: QR должен собраться сам из адреса страницы.
 *
 * Адрес задаём «боевой» (иначе блок с QR честно убирается), а скрипты
 * подкладываем из файлов: сеть тесту не нужна. canvas в jsdom пустой,
 * поэтому подменяем контекст и считаем, что именно нарисовано.
 */
async function checkIndex() {
  const html = fs
    .readFileSync(path.join(DOCS, 'index.html'), 'utf8')
    .replace(/<script src="[^"]*"><\/script>/g, '');
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    url: 'https://neonco.github.io/gamedev7/',
    pretendToBeVisual: true,
  });
  const { window } = dom;

  const drawn = [];
  window.HTMLCanvasElement.prototype.getContext = function () {
    return {
      fillStyle: '',
      fillRect(x, y, w, h) {
        drawn.push([x, y, w, h, this.fillStyle]);
      },
    };
  };

  window.eval(fs.readFileSync(path.join(ROOT, 'assets', 'qr.js'), 'utf8'));
  window.eval(fs.readFileSync(path.join(ROOT, 'assets', 'site.js'), 'utf8'));
  await new Promise((r) => setTimeout(r, 50));

  const { document } = window;
  const canvas = document.querySelector('.hero-qr canvas');
  check('блок с QR не выброшен', !!document.querySelector('.hero-qr'), true);
  check('canvas с QR нарисован', !!canvas, true);
  check('QR квадратный и не вырожденный', canvas.width > 100 && canvas.width === canvas.height, true);
  check('адрес под QR — сама страница', document.querySelector('[data-qr-url]').textContent, 'neonco.github.io/gamedev7/');
  check('модули QR нарисованы', drawn.length > 50, true);
  check('фон QR белый', drawn[0][4], '#ffffff');
  check('есть кнопка со ссылкой на установщики', !!document.querySelector('.hero-actions a[href*="drive.google.com"]'), true);
}

(async () => {
  const quizFiles = fs.readdirSync(path.join(DOCS, 'quiz')).filter((f) => f.endsWith('.html'));
  const lessonFile = fs
    .readdirSync(path.join(DOCS, 'lesson'))
    .filter((f) => f.endsWith('.html'))[0];

  for (const file of quizFiles) {
    console.log(`--- викторина ${file} ---`);
    await checkQuiz(await load(path.join('quiz', file)));
    console.log();
  }

  console.log(`--- печать шпаргалки (${lessonFile}) ---`);
  await checkPrint(await load(path.join('lesson', lessonFile)));
  console.log();

  console.log('--- стартовая страница: QR ---');
  await checkIndex();

  console.log();
  if (problems.length) {
    console.log('ПРОБЛЕМЫ:');
    problems.forEach((p) => console.log('  -', p));
    process.exit(1);
  }
  console.log('интерфейс в порядке');
})();
