# Развертывание RadioLive на Ubuntu 24.04 + nginx

Инструкция для production-развертывания Django-приложения RadioLive на VPS с Ubuntu 24.04 LTS.

**Стек:** nginx (reverse proxy + статика) → gunicorn (WSGI) → Django → SQLite.

**Сайт:** `http://r.mkazankov.ru` (поддомен `r` зоны `mkazankov.ru`).

Замените `<REPO_URL>` на URL вашего git-репозитория.

---

## 1. Предварительные требования

- VPS с **Ubuntu 24.04 LTS**, SSH-доступ с правами `sudo`
- Поддомен **`r.mkazankov.ru`** с **A-записью** (или CNAME) на IP сервера
- Публичный git-репозиторий с кодом проекта
- Открытые порты: **22** (SSH), **80** (HTTP)

**DNS:** в панели управления доменом `mkazankov.ru` создайте запись:

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `r` | IP вашего VPS |

После сохранения проверьте: `dig +short r.mkazankov.ru` или `nslookup r.mkazankov.ru`.

## 2. Подготовка сервера

Подключитесь по SSH и обновите систему:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx git
```

Создайте отдельного пользователя для приложения (не запускайте gunicorn от root):

```bash
sudo adduser --disabled-password --gecos "" radiolive
sudo mkdir -p /var/www/radiolive
sudo chown radiolive:radiolive /var/www/radiolive
```

---

## 3. Клонирование репозитория

```bash
sudo -u radiolive git clone <REPO_URL> /var/www/radiolive/app
cd /var/www/radiolive/app
```

Создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install django requests gunicorn
```

> **Примечание:** в README проекта указан Python 3.14. На Ubuntu 24.04 доступен системный Python 3.12 — для Django 6 этого достаточно.

---

## 4. Production-настройки Django

В репозитории настройки рассчитаны на разработку. Отредактируйте `config/settings.py` **на сервере**:

```bash
nano /var/www/radiolive/app/config/settings.py
```

### 4.1. SECRET_KEY

Сгенерируйте новый ключ (в активированном venv):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Подставьте результат вместо текущего значения `SECRET_KEY`. **Не коммитьте** production-ключ в git.

### 4.2. DEBUG и ALLOWED_HOSTS

```python
DEBUG = False

ALLOWED_HOSTS = ['r.mkazankov.ru']
```

### 4.3. STATIC_ROOT

После блока `STATICFILES_DIRS` добавьте:

```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

### 4.4. CSRF (рекомендуется)

При работе за nginx добавьте:

```python
CSRF_TRUSTED_ORIGINS = ['http://r.mkazankov.ru']
```

---

## 5. Инициализация приложения

Выполняйте команды от пользователя `radiolive` с активированным venv:

```bash
cd /var/www/radiolive/app
source .venv/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py refresh_stations --max-records 5000
```

Последняя команда загружает начальный каталог радиостанций из [Radio Browser](https://www.radio-browser.info/). Без лимита: `python manage.py refresh_stations`.

Проверьте права на базу данных:

```bash
ls -la /var/www/radiolive/app/db.sqlite3
```

Файл должен принадлежать пользователю `radiolive`. При необходимости:

```bash
sudo chown radiolive:radiolive /var/www/radiolive/app/db.sqlite3
```

---

## 6. systemd-сервис gunicorn

Создайте unit-файл:

```bash
sudo nano /etc/systemd/system/radiolive.service
```

Содержимое:

```ini
[Unit]
Description=RadioLive gunicorn daemon
After=network.target

[Service]
User=radiolive
Group=radiolive
WorkingDirectory=/var/www/radiolive/app
ExecStart=/var/www/radiolive/app/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/radiolive/app/radiolive.sock \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Активируйте и запустите сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable radiolive
sudo systemctl start radiolive
sudo systemctl status radiolive
```

При ошибках смотрите логи:

```bash
journalctl -u radiolive -e
```

---

## 7. Конфигурация nginx

Создайте конфиг сайта:

```bash
sudo nano /etc/nginx/sites-available/radiolive
```

Содержимое:

```nginx
server {
    listen 80;
    server_name r.mkazankov.ru;

    location /static/ {
        alias /var/www/radiolive/app/staticfiles/;
    }

    location / {
        proxy_pass http://unix:/var/www/radiolive/app/radiolive.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт и перезагрузите nginx:

```bash
sudo ln -s /etc/nginx/sites-available/radiolive /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> Если на сервере нет других сайтов и используется дефолтный конфиг nginx, его можно отключить: `sudo rm -f /etc/nginx/sites-enabled/default`, затем снова `sudo nginx -t && sudo systemctl reload nginx`.

---

## 8. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx HTTP'
sudo ufw enable
sudo ufw status
```

---

## 9. Проверка

Откройте в браузере:

| URL | Ожидаемый результат |
|-----|----------------------|
| `http://r.mkazankov.ru/` | Главная страница со списком станций |
| `http://r.mkazankov.ru/static/radio/app.css` | CSS загружается (не 404) |
| `http://r.mkazankov.ru/admin/` | Страница входа в админку |

Проверьте функциональность:

- Поиск и фильтры (страна, жанр, качество)
- Воспроизведение потока
- Избранное (сессия и аккаунт)
- Кнопка «Refresh stations DB» на главной

---

## 10. Обновление приложения (redeploy)

```bash
cd /var/www/radiolive/app
sudo -u radiolive git pull
source .venv/bin/activate
pip install django requests gunicorn
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart radiolive
```

---

## 11. Автообновление станций (опционально)

Чтобы периодически обновлять каталог станций, добавьте задачу cron для пользователя `radiolive`:

```bash
sudo crontab -u radiolive -e
```

Пример — каждый день в 03:00:

```cron
0 3 * * * cd /var/www/radiolive/app && .venv/bin/python manage.py refresh_stations --max-records 5000 >> /var/log/radiolive-refresh.log 2>&1
```

---

## 12. Типичные проблемы

### 502 Bad Gateway

- Сервис gunicorn не запущен: `sudo systemctl status radiolive`
- Неверный путь к socket в nginx или unit-файле
- Логи: `journalctl -u radiolive -e`

### Статика не загружается (нет стилей)

- Не выполнен `collectstatic` или неверный путь в `location /static/`
- Проверьте наличие файлов: `ls /var/www/radiolive/app/staticfiles/radio/`

### DisallowedHost

- Поддомен `r.mkazankov.ru` не добавлен в `ALLOWED_HOSTS` в `config/settings.py`

### Permission denied на db.sqlite3

- Файл БД должен принадлежать `radiolive`:
  ```bash
  sudo chown radiolive:radiolive /var/www/radiolive/app/db.sqlite3
  ```

### Пустой список станций

- Запустите вручную: `python manage.py refresh_stations --max-records 5000`

### CSRF-ошибка при POST-запросах

- Добавьте домен в `CSRF_TRUSTED_ORIGINS` (см. раздел 4.4)

---

## 13. Безопасность

- Развертывание выполняется по **HTTP** — пароли и сессии передаются в открытом виде. Для сайта с регистрацией пользователей рекомендуется добавить HTTPS (Certbot + Let's Encrypt).
- Смените `SECRET_KEY` — не используйте dev-ключ из репозитория.
- Держите `DEBUG = False` на production.
- Регулярно обновляйте систему: `sudo apt update && sudo apt upgrade`.
