/**
 * Вотчер для отслеживания изменений полей формы и управления режимом обхода валидации.
 *
 * Используется для валидации с поддержкой игнорирования:
 * 1. Добавляет функцию addGetParam для динамического добавления GET параметров к form action
 * 2. Отслеживает изменения всех типов полей в форме:
 *    - Стандартные: input (все типы кроме submit), textarea, select
 *    - CodeMirror редакторы (div.codemirror)
 *    - Редактируемое содержимое (contenteditable элементы)
 * 3. При изменении данных:
 *    - Удаляет класс force-ignore-validation ко кнопок (возвращает нормальный цвет)
 *    - Удаляет GET параметр из action кнопок
 *    - Скрывает сообщения об ошибках валидации (.errornote, .errorlist)
 * 4. Визуально показывает пользователю статус обхода валидации цветом кнопок
 *
 * Универсальное решение: работает для любых форм в админке, не только для лейблов.
 */

// Функция для добавления GET параметра к form action кнопки
function addGetParam(button, key, value) {
  const form = button.form; // Находим форму, в которой лежит кнопка
  const baseAction = form.getAttribute('action'); // Получаем текущий action

  // Удаляем старый параметр, если он есть
  let cleanAction = baseAction.split('?')[0];

  // Проверяем, есть ли уже в action другие GET-параметры
  const separator = cleanAction === baseAction ? '?' : '&';

  // Динамически прописываем измененный URL в formAction кнопки
  button.formAction = baseAction + separator + key + '=' + value;
}

// Функция для добавления класса force-ignore-validation ко всем submit-кнопкам формы
// Используется при клике на кнопку "Я проверил и уверен!"
function markSubmitButtonsToIgnoreValidation() {
  // Находим все submit-кнопки на странице и добавляем им класс
  // form-field-watcher.js потом отследит добавление класса через MutationObserver
  // и добавит соответствующие onclick обработчики
  document.querySelectorAll('input[type=submit]').forEach(function (btn) {
    btn.classList.add('force-ignore-validation');
  });
}

document.addEventListener('DOMContentLoaded', function () {
  // Находим все submit-кнопки администратора
  let submitButtons = document.querySelectorAll('input[type=submit]');

  // Если нет submit-кнопок, выходим (не админская форма)
  if (submitButtons.length === 0) {
    return;
  }

  // Находим форму
  let form = document.querySelector('form');
  if (!form) {
    return;
  }

  // Сохраняем оригинальный action формы
  let originalAction = form.getAttribute('action');

  // Функция для добавления onclick обработчика
  function addOnclickHandler(btn) {
    // Проверяем есть ли уже onclick
    if (!btn.getAttribute('onclick')) {
      btn.setAttribute('onclick', 'if (this.classList.contains("force-ignore-validation")) { ' +
        'const form = this.form; ' +
        'const baseAction = form.getAttribute("action") || ""; ' +
        'let cleanAction = baseAction.split("?")[0]; ' +
        'const separator = cleanAction === baseAction ? "?" : "&"; ' +
        'form.setAttribute("action", baseAction + separator + "ignore_validate=1"); ' +
        '}');
    }
  }

  // Функция для удаления onclick обработчика
  function removeOnclickHandler(btn) {
    btn.removeAttribute('onclick');
  }

  // Отслеживаем изменения всех типов полей в форме
  let formInputs = document.querySelectorAll('input:not([type=submit]), textarea, select, .codemirror, [contenteditable]');

  // Функция которая срабатывает при любом изменении
  function handleChange() {
    // При изменении любого поля:
    // 1. Удаляем класс force-ignore-validation (кнопки вернут нормальный цвет)
    // 2. Удаляем onclick обработчик
    // 3. Восстанавливаем оригинальный action формы
    submitButtons.forEach(function (btn) {
      if (btn.classList.contains('force-ignore-validation')) {
        btn.classList.remove('force-ignore-validation');
        removeOnclickHandler(btn);
      }
    });
    form.setAttribute('action', originalAction);

    // Скрываем сообщения об ошибках валидации
    let errorNotes = document.querySelectorAll('.errornote, .errorlist');
    errorNotes.forEach(function (errorElement) {
      errorElement.style.display = 'none';
    });
  }

  formInputs.forEach(function (input) {
    // Слушаем оба события: 'change' для обычных input/select
    // и 'input' для CodeMirror и других редакторов
    input.addEventListener('change', handleChange);
    input.addEventListener('input', handleChange);
  });

  // Мониторим изменение класса force-ignore-validation на кнопках
  // Используем MutationObserver для отслеживания добавления/удаления класса
  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
        let btn = mutation.target;
        if (btn.tagName === 'INPUT' && btn.type === 'submit') {
          // Если класс добавлен - навешиваем onclick
          if (btn.classList.contains('force-ignore-validation')) {
            addOnclickHandler(btn);
          }
          // Если класс удален - удаляем onclick
          else if (btn.getAttribute('onclick')) {
            removeOnclickHandler(btn);
          }
        }
      }
    });
  });

  // Настраиваем observer для отслеживания изменения класса
  submitButtons.forEach(function (btn) {
    observer.observe(btn, {attributes: true, attributeFilter: ['class']});
  });
});
