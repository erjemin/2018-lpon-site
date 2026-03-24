# Используем официальный легковесный образ Nginx на базе Alpine Linux
FROM nginx:alpine
# FROM nginx:nginx:1.25-alpine

# Удаляем стандартную конфигурацию Nginx, чтобы использовать свою
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш кастомный конфиг для внутреннего Nginx
COPY config/nginx/lpon--internal-nginx.conf /etc/nginx/conf.d/default.conf

# Копируем все содержимое папки 'public' в корневую веб-директорию Nginx
# Теперь index.html, favicons, robots.txt, и папка static/ будут доступны
COPY public/ /usr/share/nginx/html/
