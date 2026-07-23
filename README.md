# Phygital Machines — лендинг

Одностраничный сайт с интерактивными 3D-моделями.

## Как выложить на GitHub Pages

1. Создай репозиторий на github.com (например `phygital`).
2. Загрузи в него **всё содержимое** этой папки: `index.html`, `robots.txt`,
   `.nojekyll` и папку `models/`.
3. Settings → Pages → Source: `Deploy from a branch`, ветка `main`, папка `/ (root)`.
4. Через 1–2 минуты сайт будет по адресу `https://ИМЯ.github.io/phygital/`.

Файл `.nojekyll` обязателен — без него GitHub игнорирует некоторые файлы.
`robots.txt` и мета-тег `noindex` закрывают сайт от поисковиков.

## Локальный просмотр

Просто открыть `index.html` двойным кликом **не сработает** — браузер
заблокирует загрузку моделей (CORS). Нужен локальный сервер:

```
cd папка_с_сайтом
python3 -m http.server 8000
```

Затем открыть http://localhost:8000

## Модели

`models/car1.glb` — цельная машина
`models/car2.glb` — открытое шасси
`models/car3.glb` — съёмная крыша

Сжаты через gltfpack (meshopt): 63 МБ → 5.9 МБ без потери качества.

## Важно: декодер meshopt

Модели сжаты расширением `EXT_meshopt_compression`. `<model-viewer>` **не**
включает декодер для него по умолчанию, поэтому в `<head>` задан путь:

```html
<script>
  window.ModelViewerElement = window.ModelViewerElement || {};
  window.ModelViewerElement.meshoptDecoderLocation = 'vendor/meshopt_decoder.js';
</script>
```

Файл `vendor/meshopt_decoder.js` обязателен — без него в консоли будет ошибка
`setMeshoptDecoder must be called before loading compressed files`,
и модели не отрисуются.
