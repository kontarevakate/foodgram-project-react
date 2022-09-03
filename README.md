![Foodgram workflow](https://github.com/kontarevakate/foodgram-project-react/actions/workflows/main.yml/badge.svg)

# Публичный IP-адрес
Проект доступен по адресу: http://158.160.1.232
# Описание:
Сайт Foodgram, «Продуктовый помощник» - это сервис, на котором пользователи смогут публиковать рецепты, подписываться на публикации других пользователей, добавлять понравившиеся рецепты в список «Избранное», а перед походом в магазин скачивать сводный список продуктов, необходимых для приготовления одного или нескольких выбранных блюд.

# Шаблон наполнения .env файла:

DB_ENGINE=...
DB_NAME=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
DB_HOST=...
DB_PORT=...

# Установка:

Клонировать репозиторий и перейти в него в командной строке:

```
git clone git@github.com:kontarevakate/foodgram-project-react.git
```

```
cd foodgram-project-react
```

Запустить docker-compose:

```
docker-compose up -d --build
```

Выполнить миграции:

```
docker-compose exec web python manage.py migrate
```

Создать суперпользователя:

```
docker-compose exec web python manage.py createsuperuser
```
Подгрузить статику:

```
docker-compose exec web python manage.py collectstatic --no-input
```
