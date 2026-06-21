/**
 * Вотчер для отслеживания изменений полей формы и сброса состояния submit-кнопок.
 *
 * Используется для валидации с поддержкой игнорирования:
 * 1. Сохраняет оригинальные значения submit-кнопок при загрузке
 * 2. Отслеживает изменения всех типов полей в форме:
 *    - Стандартные: input (все типы кроме submit), textarea, select
 *    - CodeMirror редакторы (div.codemirror)
 *    - Редактируемое содержимое (contenteditable элементы)
 * 3. При изменении данных:
 *    - Восстанавливает оригинальные значения submit-кнопок
 *    - Скрывает сообщения об ошибках валидации (.errornote, .errorlist)
 * 4. Это отменяет флаг 'ignore_validate' если пользователь редактирует данные
 *
 * Универсальное решение: работает для любых форм в админке, не только для лейблов.
 * Селекторы легко расширяются для поддержки других типов полей.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Сохраняем оригинальные значения submit-кнопок администратора
    let originalValues = {};
    let submitButtons = document.querySelectorAll('input[type=submit]');

    // Если нет submit-кнопок, выходим (не админская форма)
    if (submitButtons.length === 0) {
        return;
    }

    // Запоминаем оригинальные значения каждой submit-кнопки
    submitButtons.forEach(function(btn) {
        originalValues[btn.name] = btn.value;
    });

    // Отслеживаем изменения всех типов полей в форме
    // Селекторы охватывают:
    // - text input (кроме submit), textarea, select, checkbox, radio и т.д.
    // - CodeMirror редакторы (div.codemirror)
    // - contenteditable элементы
    let formInputs = document.querySelectorAll('input:not([type=submit]), textarea, select, .codemirror, [contenteditable]');

    // Функция которая срабатывает при любом изменении
    function handleChange() {
        // При изменении любого поля восстанавливаем оригинальные значения submit-кнопок
        submitButtons.forEach(function(btn) {
            btn.value = originalValues[btn.name];
            // Удаляем класс force-ignore-validation при редактировании
            btn.classList.remove('force-ignore-validation');
        });

        // Скрываем сообщения об ошибках валидации
        let errorNotes = document.querySelectorAll('.errornote, .errorlist');
        errorNotes.forEach(function(errorElement) {
            errorElement.style.display = 'none';
        });
    }

    formInputs.forEach(function(input) {
        // Слушаем оба события: 'change' для обычных input/select
        // и 'input' для CodeMirror и других редакторов
        input.addEventListener('change', handleChange);
        input.addEventListener('input', handleChange);
    });
});

