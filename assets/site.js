/* Курс «Разработка игр, 7 класс» — поведение страниц.
   Прогресс живёт в localStorage и переносится между ноутбуками файлом. */

(() => {
  'use strict';

  const KEY = 'gd7-progress';
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  /* ---------- прогресс ---------- */
  const Store = {
    read() {
      try {
        const raw = localStorage.getItem(KEY);
        return raw ? JSON.parse(raw) : {};
      } catch (e) {
        return {};
      }
    },
    write(data) {
      try {
        localStorage.setItem(KEY, JSON.stringify(data));
      } catch (e) {
        /* приватный режим — молча живём без сохранения */
      }
    },
    get(slug) {
      return this.read()[slug] || {};
    },
    set(slug, key, value) {
      const all = this.read();
      const lesson = all[slug] || (all[slug] = {});
      if (value === false || value === '' || value == null) delete lesson[key];
      else lesson[key] = value;
      this.write(all);
    },
  };

  const isDone = (value) => value === true || (typeof value === 'string' && value.trim() !== '');

  function ratio(done, total) {
    if (!total) return 0;
    return Math.max(0, Math.min(1, done / total));
  }

  /* ---------- страница урока ---------- */
  function initLesson() {
    const bar = $('[data-lesson-progress]');
    if (!bar) return;
    const slug = bar.dataset.lessonProgress;
    const note = $(`[data-lesson-note="${slug}"]`);
    const fields = $$('[data-k]');
    const saved = Store.get(slug);

    fields.forEach((el) => {
      const key = el.dataset.k;
      const value = saved[key];
      if (el.type === 'checkbox') el.checked = value === true;
      else if (typeof value === 'string') el.value = value;
    });

    function refresh() {
      const total = fields.length;
      let done = 0;
      fields.forEach((el) => {
        const value = el.type === 'checkbox' ? el.checked : el.value;
        if (isDone(el.type === 'checkbox' ? el.checked : el.value)) done += 1;
      });
      const r = ratio(done, total);
      const fill = bar.querySelector('span');
      if (fill) fill.style.width = `${Math.round(r * 100)}%`;
      bar.classList.toggle('done', total > 0 && done === total);
      if (note) {
        note.textContent = total
          ? done === total
            ? `Пункты урока отмечены полностью — ${done} из ${total}`
            : `Отмечено ${done} из ${total}`
          : '';
      }
    }

    fields.forEach((el) => {
      const handler = () => {
        Store.set(slug, el.dataset.k, el.type === 'checkbox' ? el.checked : el.value);
        refresh();
      };
      el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', handler);
    });

    refresh();
  }

  /* ---------- карта курса ---------- */
  async function initIndex() {
    const q = $('#q');
    if (!q) return;

    let lessons = [];
    try {
      const res = await fetch('data/lessons.json', { cache: 'no-store' });
      if (res.ok) lessons = await res.json();
    } catch (e) {
      lessons = [];
    }

    const totals = {};
    lessons.forEach((l) => {
      totals[l.slug] = l.checks || 0;
    });

    function paintProgress() {
      const all = Store.read();
      let doneAll = 0;
      let totalAll = 0;
      $$('[data-lesson-progress]').forEach((bar) => {
        const slug = bar.dataset.lessonProgress;
        const total = totals[slug] || 0;
        const lesson = all[slug] || {};
        const done = Object.keys(lesson).filter((k) => isDone(lesson[k])).length;
        doneAll += Math.min(done, total);
        totalAll += total;
        const fill = bar.querySelector('span');
        if (fill) fill.style.width = `${Math.round(ratio(done, total) * 100)}%`;
        bar.classList.toggle('done', total > 0 && done >= total);
        const card = bar.closest('.lcard');
        if (card) {
          const pct = total ? Math.round(ratio(done, total) * 100) : 0;
          card.title = total
            ? `Отмечено ${Math.min(done, total)} из ${total} (${pct}%)`
            : 'В уроке нет пунктов для отметки';
        }
      });
      const prog = $('#prog');
      if (prog) {
        prog.textContent = totalAll
          ? `прогресс ${doneAll} / ${totalAll}`
          : '';
      }
    }

    function filter() {
      const query = q.value.trim().toLowerCase();
      let shown = 0;
      $$('.lcard').forEach((card) => {
        const hay = [
          card.dataset.num,
          card.dataset.title,
          card.dataset.artifact,
          card.dataset.cmds,
        ]
          .join(' ')
          .toLowerCase();
        const hit = !query || query.split(/\s+/).every((word) => hay.includes(word));
        card.classList.toggle('hide', !hit);
        if (hit) shown += 1;
      });
      $$('.sprint').forEach((sprint) => {
        const any = Array.from(sprint.querySelectorAll('.lcard')).some(
          (c) => !c.classList.contains('hide')
        );
        sprint.classList.toggle('hide', !any);
      });
      const empty = $('#empty');
      if (empty) empty.style.display = shown ? 'none' : 'block';
      const clear = $('#clear');
      if (clear) clear.style.display = query ? 'inline-block' : 'none';
    }

    q.addEventListener('input', filter);
    q.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        q.value = '';
        filter();
      }
    });
    const clear = $('#clear');
    if (clear) {
      clear.addEventListener('click', () => {
        q.value = '';
        filter();
        q.focus();
      });
    }

    const exportBtn = $('#export');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        const blob = new Blob([JSON.stringify(Store.read(), null, 2)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'progress-gamedev7.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }

    const importInput = $('#import');
    if (importInput) {
      importInput.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const data = JSON.parse(String(reader.result));
            const merged = Object.assign({}, Store.read(), data);
            Store.write(merged);
            paintProgress();
          } catch (err) {
            alert('Не получилось прочитать файл прогресса.');
          }
          importInput.value = '';
        };
        reader.readAsText(file);
      });
    }

    filter();
    paintProgress();
  }

  /* ---------- копирование кода ---------- */
  function initCopy() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-copy]');
      if (!btn) return;
      const block = btn.closest('.codeblock');
      const code = block && block.querySelector('pre code');
      if (!code) return;
      const text = code.innerText;
      const done = () => {
        const was = btn.textContent;
        btn.textContent = 'Скопировано ✓';
        setTimeout(() => {
          btn.textContent = was;
        }, 1500);
      };
      const fallback = () => {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand('copy');
          done();
        } catch (err) {
          /* ничего не поделать */
        }
        document.body.removeChild(ta);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(fallback);
      } else {
        fallback();
      }
    });
  }

  /* ---------- тема и наверх ---------- */
  function initTheme() {
    const root = document.documentElement;
    const meta = document.querySelector('meta[name=theme-color]');
    const sync = () => {
      if (meta) meta.setAttribute('content', root.dataset.theme === 'dark' ? '#15171a' : '#fbfaf7');
    };
    sync();
    const btn = $('#theme');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const dark = root.dataset.theme === 'dark';
      root.dataset.theme = dark ? '' : 'dark';
      try {
        localStorage.setItem('gd7-theme', dark ? 'light' : 'dark');
      } catch (e) {}
      sync();
    });
  }

  function initTop() {
    const btn = $('#top');
    if (!btn) return;
    const onScroll = () => btn.classList.toggle('show', window.scrollY > 400);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    btn.addEventListener('click', () => {
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    });
  }

  /* ---------- печать шпаргалки и документов ---------- */
  function initCheatPrint() {
    document.addEventListener('click', (e) => {
      const cheat = e.target.closest('[data-print-cheat]');
      const doc = e.target.closest('[data-print-doc]');
      const btn = cheat || doc;
      if (!btn) return;
      // шпаргалка печатается одна, документ — целиком, но без навигации
      const cls = cheat ? 'print-cheat' : 'print-doc';
      const was = btn.textContent;
      btn.textContent = 'Готовим печать…';
      document.body.classList.add(cls);
      window.print();
      // ждём, пока браузер закроет окно печати
      setTimeout(() => {
        document.body.classList.remove(cls);
        btn.textContent = was;
      }, 500);
    });
  }

  /* ---------- викторина ---------- */
  function initQuiz() {
    const root = document.querySelector('[data-quiz]');
    if (!root) return;

    const slug = root.dataset.quiz;
    const key = 'gd7-quiz:' + slug;
    const questions = Array.from(root.querySelectorAll('.quiz-q'));
    const scoreEl = $('#quiz-score');
    const checkBtn = $('#quiz-check');
    const resetBtn = $('#quiz-reset');

    const read = () => {
      try {
        return JSON.parse(localStorage.getItem(key)) || {};
      } catch (e) {
        return {};
      }
    };
    const write = (data) => {
      try {
        localStorage.setItem(key, JSON.stringify(data));
      } catch (e) {}
    };

    let answers = read();
    let checked = false;

    function select(question, index) {
      if (checked) return;
      answers[question.dataset.q] = index;
      write(answers);
      question.querySelectorAll('.opt').forEach((opt) => {
        opt.classList.toggle('picked', Number(opt.dataset.i) === index);
      });
    }

    function verdicts() {
      let right = 0;
      questions.forEach((question) => {
        const picked = answers[question.dataset.q];
        const options = Array.from(question.querySelectorAll('.opt'));
        const correct = options.findIndex((opt) => opt.dataset.ok === '1');
        const isRight = picked !== undefined && Number(picked) === correct;
        if (isRight) right += 1;

        options.forEach((opt) => {
          opt.classList.remove('good', 'bad', 'picked');
          opt.disabled = true;
          const index = Number(opt.dataset.i);
          if (index === correct) opt.classList.add('good');
          else if (index === Number(picked)) opt.classList.add('bad');
        });

        // разбор показываем после проверки — по нему и учатся
        const explain = question.querySelector('.quiz-explain');
        if (explain) explain.hidden = false;
        question.classList.add('done');
      });
      return right;
    }

    function paint() {
      questions.forEach((question) => {
        const picked = answers[question.dataset.q];
        question.querySelectorAll('.opt').forEach((opt) => {
          opt.classList.toggle('picked', Number(opt.dataset.i) === Number(picked));
        });
      });
      const answered = Object.keys(answers).length;
      if (scoreEl && !checked) {
        scoreEl.textContent = answered ? `отвечено ${answered} из ${questions.length}` : '';
      }
    }

    root.addEventListener('click', (e) => {
      const opt = e.target.closest('.opt');
      if (!opt) return;
      select(opt.closest('.quiz-q'), Number(opt.dataset.i));
      paint();
    });

    if (checkBtn) {
      checkBtn.addEventListener('click', () => {
        const answered = Object.keys(answers).length;
        if (answered < questions.length && !checked) {
          const left = questions.length - answered;
          if (!confirm(`Осталось вопросов без ответа: ${left}. Проверить всё равно?`)) return;
        }
        checked = true;
        const right = verdicts();
        if (scoreEl) {
          scoreEl.textContent = `правильно ${right} из ${questions.length}`;
          scoreEl.classList.toggle('good', right === questions.length);
        }
        checkBtn.textContent = 'Проверено';
        checkBtn.disabled = true;
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        answers = {};
        checked = false;
        write(answers);
        questions.forEach((question) => {
          question.classList.remove('done');
          const explain = question.querySelector('.quiz-explain');
          if (explain) explain.hidden = true;
          question.querySelectorAll('.opt').forEach((opt) => {
            opt.classList.remove('picked', 'good', 'bad');
            opt.disabled = false;
          });
        });
        if (scoreEl) {
          scoreEl.textContent = '';
          scoreEl.classList.remove('good');
        }
        if (checkBtn) {
          checkBtn.textContent = 'Проверить';
          checkBtn.disabled = false;
        }
      });
    }

    paint();
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initCopy();
    initTop();
    initLesson();
    initIndex();
    initCheatPrint();
    initQuiz();
  });
})();
