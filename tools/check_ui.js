/**
 * Проверка интерфейса без браузера: викторина и печать шпаргалки.
 *
 * Требует jsdom:
 *     npm install jsdom
 *     node tools/check_ui.js
 *
 * Проверяется то, что нельзя проверить статически: клики по вариантам,
 * подсчёт результата, раскрытие разборов, сброс и режим печати.
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
  if (problems.length) {
    console.log('ПРОБЛЕМЫ:');
    problems.forEach((p) => console.log('  -', p));
    process.exit(1);
  }
  console.log('интерфейс в порядке');
})();
