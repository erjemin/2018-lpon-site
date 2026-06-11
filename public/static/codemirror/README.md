# CodeMirror 6 static bundle

Эта папка содержит готовый результат сборки CodeMirror 6 для админки Django.

Главный файл здесь — `editor.js`. Его не нужно править вручную: это собранный и
минифицированный бандл.

Если нужна более свежая версия CodeMirror, меняй сборку в
`frontend-assembly/build-codemirror6.sh` и затем заново запускай:

```bash
bash ./frontend-assembly/build-codemirror6.sh
```

После пересборки в этой папке должен обновиться только `editor.js`.
