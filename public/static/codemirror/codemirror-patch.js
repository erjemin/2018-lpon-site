/**
 * CodeMirror 6 - Height Control Patch
 *
 * Этот патч перехватывает создание CodeMirror редакторов и копирует
 * атрибут data-height с textarea на создаваемый wrapper div.
 *
 * Использование в admin.py:
 *   textarea widget: attrs={'data-height': '50px', 'data-codemirror-editor': '1'}
 *
 * Загружается ПОСЛЕ editor.js через Media в Admin класс.
 */

(function () {
  'use strict';

  /**
   * Применяем высоту к уже созданным wrapper'ам
   * (CodeMirror уже загрузился и создал обёртки)
   */
  function applyHeightsToExistingWrappers() {
    // Находим все textarea'ы с data-codemirror-editor
    document.querySelectorAll('textarea[data-codemirror-editor]').forEach((textarea) => {
      // Соседний div (wrapper, созданный CodeMirror)
      const wrapper = textarea.previousElementSibling;

      // Проверяем что это действительно wrapper CodeMirror
      if (wrapper && wrapper.classList && wrapper.classList.contains('cm6-editor-wrapper')) {
        // Копируем data-height на style если указано
        if (textarea.dataset.height) {
          wrapper.style.height = textarea.dataset.height;
        }

        // Копируем data-width на style если указано (для ширины)
        if (textarea.dataset.width) {
          wrapper.style.width = textarea.dataset.width;
          wrapper.style.minWidth = textarea.dataset.width;

          // Также устанавливаем ширину на сам .cm-editor внутри wrapper
          // Используем !important чтобы переопределить flex: 1 1 auto из CSS
          const cmEditor = wrapper.querySelector('.cm-editor');
          // if (cmEditor) {
          //   cmEditor.style.cssText = `width: ${textarea.dataset.width} !important; flex: 0 0 auto;`;
          // }
        }

        // Копируем классы с textarea если они есть
        // (например cm6-editor-wrapper-xs, cm6-editor-wrapper-sm и т.д.)
        if (textarea.className) {
          // Добавляем классы из textarea (сохраняя cm6-editor-wrapper)
          textarea.className.split(' ').forEach((cls) => {
            if (cls && cls !== 'cm6-editor-wrapper') {
              wrapper.classList.add(cls);
            }
          });
        }
      }
    });
  }

  // Применяем высоты когда DOM готов
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyHeightsToExistingWrappers);
  } else {
    // DOM уже загружен
    applyHeightsToExistingWrappers();
  }

  // Также применяем для динамически добавленных элементов (если загружают CodeMirror после инициализации)
  const observer = new MutationObserver(() => {
    applyHeightsToExistingWrappers();
  });

  observer.observe(document, {
    childList: true,
    subtree: true,
  });
})();

