# Стадия сборки
FROM node:18-alpine as build

WORKDIR /app

# Копируем package.json и устанавливаем зависимости
COPY package*.json ./
RUN npm ci --only=production

# Копируем исходный код и собираем приложение
COPY . .
RUN npm run build

# Стадия для раздачи статики (опционально, можно использовать nginx)
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]о